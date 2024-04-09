#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Apr  8 13:37:15 2024

@author: yarov3so
"""

from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup as bs
import json
import re
import pandas as pd
import numpy as np
import statsmodels.api as sm
from matplotlib import pyplot as plt
import seaborn as sns 
from datetime import datetime
import requests
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
from io import BytesIO
import base64

sns.set()

def scraping_initializer(): # this function loads the Chrome webdriver and logs into clublog.org

    global driver

    driver = webdriver.Chrome()
    driver.get('https://clublog.org/loginform.php')
    
    username_input = WebDriverWait(driver, 1).until(EC.presence_of_element_located((By.NAME, 'fEmail')))
    password_input = WebDriverWait(driver, 1).until(EC.presence_of_element_located((By.NAME, 'fPassword')))
    login_button = WebDriverWait(driver, 1).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="submit"]'))) 
    
    username_input.send_keys('yaroveso@gmail.com')
    password_input.send_keys('bootcamp') # for the sake of simplicity
    login_button.click()
    
    driver.get('https://clublog.org/propagation.php')


def scrape_graphs(driver): # scrapes the bar charts from a single page

    soup=bs(driver.page_source)
    qso_count={}
    propagation_charts=soup.find_all('table',class_='propagationChart2')
    
    for i in range(11):
    
        band=int(re.search(r'(\d+)m',propagation_charts[i].text).group(1))
        qso_total=int(re.search(r' (\d+) ',propagation_charts[i].text).group(1))
        qso_count[band]={}
        
        if qso_total==0:
    
            for num in range(24):
                qso_count[band][num]=0
                
            continue
        
        chart=propagation_charts[i].find_all('img',class_='real')
    
        height_total=sum([float(re.findall(r'\d+\.?\d*',x.get('height'))[0]) for x in chart])
             
        for el in chart:
            
            time=int(re.search(r'_(\d+)',el.get('id')).group(1))
            height=float(re.findall(r'\d+\.?\d*',el.get('height'))[0])
            qso_count[band][time]=round(height*qso_total/height_total) # using the pixel heights of bars in the bar chart to infer QSO counts
    
            for num in range(24):
                
                if num not in qso_count[band].keys():
                    qso_count[band][num]=0 # in the absence of a bar, infer that the QSO count is null

    return qso_count
    

def select_params(Source,Dest,Month,Min_sfi,Max_sfi): # selects parameters for the website to display the relevant bar charts 
    
    source = Select(driver.find_element(By.ID, 'formsource'))
    source.select_by_visible_text(Source)
    dest = Select(driver.find_element(By.ID, 'formdest'))
    dest.select_by_visible_text(Dest)
    month = Select(driver.find_element(By.NAME, 'month'))
    month.select_by_visible_text(Month)
    min_sfi = Select(driver.find_element(By.NAME, 'formsfi'))
    min_sfi.select_by_visible_text(str(Min_sfi))
    max_sfi = Select(driver.find_element(By.NAME, 'formusfi'))
    max_sfi.select_by_visible_text(str(Max_sfi))
    

def scrape_range(source,dest,sfi_invl_size): # Scrapes all QSO data for QSOs occuring between a given source and a given destination
                                             # SFI interval size has to be one of: [20, 25, 30, 50, 60, 100]

    qso_source_to_dest={}
    
    months=[x.text for x in Select(driver.find_element(By.NAME, 'month')).options]

    for month in months:

        print(f'    Month: {month}')
        print(f'        SFI range: 0 to {sfi_invl_size}')
        qso_source_to_dest[month]={}
        select_params(source,dest,month,'No limit',sfi_invl_size)
        run_report=WebDriverWait(driver, 1).until(EC.element_to_be_clickable((By.XPATH, '//*[@type="submit"]'))) 
        run_report.click()
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'chart_160')))
        qso_source_to_dest[month][f'(0,{sfi_invl_size})']=scrape_graphs(driver) # unfortunately, JSON doesn't support tuple indices

        l=sfi_invl_size
        h=2*sfi_invl_size
        
        while h<=300:

            print(f'        SFI range: {l} to {h}')
            select_params(source,dest,month,l,h)
            run_report=WebDriverWait(driver, 1).until(EC.element_to_be_clickable((By.XPATH, '//*[@type="submit"]'))) 
            run_report.click()
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'chart_160')))
            qso_source_to_dest[month][f'({l},{h})']=scrape_graphs(driver)
            l=h
            h+=sfi_invl_size

    return qso_source_to_dest
    

def make_json(source,dest_list,sfi_invl_size,filename='qso_data_dump.json'): # SFI interval size has to be one of: [20, 25, 30, 50, 60, 100]
                                                                             # source must be a string and dest_list must be a list. Please consult documentation for a list of available countries.
    scraping_initializer()

    print('Grab a beer! This will take a while...')
    
    mydict={}
    
    for dest in dest_list: # loops over all destinations in the list
        print(f'Pulling QSO data between {source} and {dest}...')
        mydict[dest]=scrape_range(source,dest,sfi_invl_size)

    mydict_str = json.dumps(mydict, indent=4)
    
    with open(filename, "w") as f: # dumps the scraped data into a JSON file
        
        print(f'Dumping dataset to {filename}...')
        f.write(mydict_str)

    print('Done!')

    return mydict

def import_dataset(path_to_dataset='qso_data_dump.json'): # loads the qso dataset to be used for analysis and recommendation engines 
    
    global qso_dataset
    
    with open(path_to_dataset, "r") as f:
        qso_dataset = json.load(f)
        
    print('QSO dataset loaded successfully.')
    
    return qso_dataset # MUST BE USED WITH SEMICOLON to prevent python kernel from freezing/panicking due to size of the dataset!

def midpoint(mystr): # used for calculating the midpoints of SFI range intervals
    
    tup=eval(mystr)
    return (tup[0]+tup[1])/2

def time_range_maker(hour,tolerance): # gives a list of all times (hours in 24-hour time) that are at most a 'tolerance' value away from a given 'hour'
    
    if hour-tolerance<0 and hour+tolerance<24:
        time_range=list(range((hour-tolerance)%24,24))+list(range(0,hour+tolerance+1))
    elif hour-tolerance>=0 and hour+tolerance>=24:
        time_range=list(range(hour-tolerance,24))+list(range(0,((hour+tolerance)%24) +1))
    elif hour-tolerance>=0 and hour+tolerance<24:
        time_range=list(range(hour-tolerance,hour+tolerance+1))
    else:
        time_range=list(range(24))

    return time_range
    
import_dataset()  
    
def tree_sum(mask,tree=qso_dataset): # uses a mask (list) to sum over the leaves of a dictionary tree 
                                     # can be generalized to other aggregation functions, but this is not necessary for this project
    if len(mask)==1:                 
        
        if len(mask[0])==0:
            return sum([tree[key] for key in tree])
        else:
            return sum([tree[key] for key in mask[0]])
            
    else:
        
        if len(mask[0])==0:
            return sum([tree_sum(mask[1:],tree[key]) for key in tree])
        else:
            return sum([tree_sum(mask[1:],tree[key]) for key in mask[0]])

def get_sfi(): # scrapes the current SFI in real time from WM7D's website - will sometimes fail when SFI info is getting updated on the website
    
    response = requests.get('https://www.wm7d.net/hamradio/solar/')
    soup=bs(response.content,features="html.parser")
    
    return int(soup.find_all('font')[2].find('b').text)

def make_plotting_data():
    
    global destinations
    global coefs
    global qso_count_sig
    
    destinations=list(qso_dataset.keys())
    coefs={}
    qso_count_sig={}
    
    # Fecthing all SFI ranges and bands
    first_dest=list(qso_dataset.keys())[0]
    sfi_ranges=list(qso_dataset[first_dest]['All'].keys())
    del sfi_ranges[1] # We exclude the range (20,40)
    bands=list(qso_dataset[first_dest]['All'][sfi_ranges[0]].keys())
    
    for k in range(len(destinations)):
        
        dest=destinations[k]
        qso_count_sig[dest]={}
        coefs[dest]={}
        
        for band in bands:
            
            # Constructing QSO count significance to be plotted for each destination and band 
            y=[]
            for sfi_range in sfi_ranges: 
                qso_count=tree_sum([[dest],['All'],[sfi_range],[band],[]]) # Number of contacts occuring on a given HF band between source and given destination for a specific SFI range 
                qso_count_all_dest = tree_sum([[],['All'],[sfi_range],[band],[]]) # Number of contacts occuring on a given HF band between source and ALL documented destinations for a specific SFI range 
                if qso_count_all_dest!=0:
                    y.append(qso_count/qso_count_all_dest)
                else:
                    y.append(0)  
    
            qso_count_sig[dest][band]=y
    
            # Analyzing the strength and direction of the relationship between QSO count significance and SFI
            if np.mean(y)!=0:
                y=y/np.mean(y) # rescaling y by the mean ensures that we are able to use the linear coefficient from OLS to faithfully compare the effect of SFI on QSO count significance across different bands and even different destinations
                               # heuristically, it is a way to ensure that the linear coefficients from OLS capture the actual effect of SFI on QSO count significance without being affected by the differing scales of QSO count significance vs SFI relationships
            
            model=sm.OLS(y,sm.add_constant([midpoint(x) for x in sfi_ranges])).fit()
            coefs[dest][band]=(model.params,model.bse) 
            
make_plotting_data()
            
def qso_count_sig_for_dest(month, band, hour, tolerance=0, dataset=qso_dataset): # Returns pandas dataframe whose indices are SFI ranges and whose columns are QSO count significances for each country
    
    if dataset==None:
        try:
            dataset=import_dataset('qso_data_dump.json')
        except:
            ValueError("QSO Dataset not found! Must either import one by running import_dataset('filename.json'); or scrape one using make_json and then import it.")
                         
    qso_dict={}

    # Getting SFI ranges
    first_dest=list(dataset.keys())[0]
    sfi_ranges=list(dataset[first_dest]['All'].keys())

    time_range=time_range_maker(hour,tolerance)

    for dest in dataset.keys():

        # Constructing QSO count significance
        y=[]
        for sfi_range in sfi_ranges: 
            qso_count=tree_sum([[dest],[month],[sfi_range],[str(band)],[str(hr) for hr in time_range]],dataset) # Number of contacts occuring on a given HF band in a specified time range in a given month between source and a given destination for a specific SFI range                                             
            qso_count_all_dest = tree_sum([[],[month],[sfi_range],[str(band)],[str(hr) for hr in time_range]],dataset) # Number of contacts occuring on a given HF band in a specified time range in a given month between source and ALL documented destinations for a specific SFI range
            if qso_count_all_dest!=0:
                y.append(qso_count/qso_count_all_dest)
            else:
                y.append(0)  
    
        qso_dict[dest]=y

    mydf = pd.DataFrame(qso_dict)
    mydf.index=sfi_ranges
    
    return mydf 

def qso_count_sig_for_bands(month, hour, tolerance=0, dataset=qso_dataset): # Returns pandas dataframe whose indices are SFI ranges and whose columns are QSO count significances for each band
    
    if dataset==None:
        try:
            dataset=import_dataset('qso_data_dump.json')
        except:
            ValueError("QSO Dataset not found! Must either import one by running import_dataset('filename.json'); or scrape one using make_json and then import it.")
                         
    qso_dict={}

    # Getting SFI ranges and bands
    first_dest=list(dataset.keys())[0]
    sfi_ranges=list(dataset[first_dest]['All'].keys())
    bands=list(dataset[first_dest]['All'][sfi_ranges[0]].keys())

    time_range=time_range_maker(hour,tolerance)

    for band in bands:

        # Constructing QSO count significance (analogous version): the ratio of QSO counts occuring on a given band to QSO counts occuring on all the documented bands.
        y=[]
        for sfi_range in sfi_ranges:  
                                                                      
            qso_count = tree_sum([[],[month],[sfi_range],[band],[str(hr) for hr in time_range]],dataset) # Number of contacts occuring in a specified time range on a given HF band originating at a given source in a given month for a specific SFI range 
            qso_count_all_bands = tree_sum([[],[month],[sfi_range],[],[str(hr) for hr in time_range]],dataset) # Number of contacts occuring in a specified time range on all HF bands originating at a given source in a given month for a specific SFI range 
            
            if qso_count_all_bands!=0:
                y.append(qso_count/qso_count_all_bands)
            else:
                y.append(0)  
    
        qso_dict[band]=y

    mydf = pd.DataFrame(qso_dict)
    mydf.index=sfi_ranges
    
    return mydf 

# Initialize the Dash app
app = dash.Dash(__name__,external_stylesheets=['https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css'])
app.title = 'QSO Prediction Tools'

month_names = {
1: 'January',
2: 'February',
3: 'March',
4: 'April',
5: 'May',
6: 'June',
7: 'July',
8: 'August',
9: 'September',
10: 'October',
11: 'November',
12: 'December'}

month=month_names[datetime.now().month]
hour=datetime.now().hour
sfi=get_sfi()

app.layout =html.Div([
    
    html.Div(style={'height': '20px'}),
    
    html.Div([html.H1('QSO Prediction Tools'), html.Div(html.Em('For radio amateurs located in Canada')), html.Div('By yarov3so (VA2ZLT)',style={'margin-bottom':'10px'}),
              
        dcc.Interval(
        id='update-time',
        interval=1000,  
        n_intervals=0
    ),
    
    html.Div(id='updated-time', style={'textAlign': 'center'}),
    
    dcc.Interval(
    id='update-sfi',
    interval=3600000,  
    n_intervals=0
    ),
    
    html.Div(id='updated-sfi', style={'textAlign': 'center'}),
    
    dcc.Interval(
    id='update-hour',
    interval=3600000,  
    n_intervals=0
    ),
    
    dcc.Interval(
    id='update-month',
    interval=3600000,  
    n_intervals=0
    ),
    
    ],style={'text-align': 'center','margin-bottom':'30px'}),
    
    
    html.Div([
    
    html.Div([
        
        html.Div([
        
        html.H2("Destination prediction engine",style={'text-align': 'center','margin-bottom':'50px'}), 
        
        html.Div([
            html.H4('HF band:',style={'margin-right': '20px'}),
            dcc.Dropdown(
                id='band',
                placeholder='Select a band...',
                options=[
                    {'label': '6m', 'value': 6},
                    {'label': '10m', 'value': 10},
                    {'label': '12m', 'value': 12},
                    {'label': '15m', 'value': 15},
                    {'label': '17m', 'value': 17},
                    {'label': '20m', 'value': 20},
                    {'label': '30m', 'value': 30},
                    {'label': '40m', 'value': 40},
                    {'label': '60m', 'value': 60},
                    {'label': '80m', 'value': 80},
                    {'label': '160m', 'value': 160}
                ],
                value=10,  
                clearable=False,
                multi=False,
                style={'width': '70px'}
                )], style={'display': 'flex', 'flex-direction': 'row', 'justify-content': 'space-between'}),

        html.Div([
            html.H4('Month:',style={'margin-right': '20px'}),
            dcc.Dropdown(
                id='month',
                options=[
                    {'label': 'All', 'value': 'All'},
                    {'label': 'January', 'value': 'January'},
                    {'label': 'February', 'value': 'February'},
                    {'label': 'March', 'value': 'March'},
                    {'label': 'April', 'value': 'April'},
                    {'label': 'May', 'value': 'May'},
                    {'label': 'June', 'value': 'June'},
                    {'label': 'July', 'value': 'July'},
                    {'label': 'August', 'value': 'August'},
                    {'label': 'September', 'value': 'September'},
                    {'label': 'October', 'value': 'October'},
                    {'label': 'November', 'value': 'November'},
                    {'label': 'December', 'value': 'December'}
                ],
                value=month, 
                style={'width': '120px'},
                placeholder='Select a month...',
                clearable=False,
                multi=False)], style={'display': 'flex', 'flex-direction': 'row', 'align-items': 'center', 'justify-content': 'space-between'}),
        
        html.Div([
            html.H4('Hour:',style={'margin-right': '20px'}),
            dcc.Dropdown(
                id='hour',
                options=[{'label':str(i),'value':i} for i in range(24)],
                style={'width': '60px'},
                value=hour, 
                clearable=False,
                placeholder='Select an hour...',
                multi=False)], style={'display': 'flex', 'flex-direction': 'row', 'align-items': 'center','justify-content': 'space-between'}),
        html.Div([
            html.H4('Tolerance:',style={'margin-right': '20px'}),
            dcc.Dropdown(
                id='tolerance',
                options=[{'label':str(i),'value':i} for i in range(13)],
                value=1, 
                style={'width': '60px'},
                clearable=False,
                placeholder='Select a tolerance...',
                multi=False)], style={'display': 'flex', 'flex-direction': 'row', 'align-items': 'center','justify-content': 'space-between'}),
        html.Div([
            html.H4('SFI:'),
            dcc.Input(
                id='sfi',
                type='number',
                style={'width': '70px'},
                placeholder='Enter SFI value...',
                value=sfi)], style={'display': 'flex', 'flex-direction': 'row', 'align-items': 'center','justify-content': 'space-between'}),
        html.Div([
            html.H4('Consider adjacent ranges:'),
            dcc.Dropdown(
                id='adjacent_ranges',
                options=[{'label':'Yes','value':True},{'label':'No','value':False}],
                value=True,
                multi=False,
                style={'width': '70px'},
                clearable=False)], style={'display': 'flex', 'flex-direction': 'row', 'align-items': 'center','justify-content': 'space-between'}),
        html.Div([
        html.H4('Top'),
        dcc.Input(
            id='top',
            style={'width': '60px'},
            type='number',
            value=10)], style={'display': 'flex', 'flex-direction': 'row', 'align-items': 'center','justify-content': 'space-between'}),
        
        html.Div(id='output-dataframe-app1',style={'margin-top': '50px','backgroundColor': 'white'})
        
    ],style={'margin': 'auto', 'text-align': 'left',"border": "2px solid black","padding": "20px",'backgroundColor': '#FFFFE0'}),
    
    html.Div([
        
        html.H2("Band prediction engine",style={'text-align': 'center','margin-bottom':'50px'}), 
    
        html.Div([
            html.H4('Month:',style={'margin-right': '20px'}),
            dcc.Dropdown(
                id='month_bd',
                options=[
                    {'label': 'All', 'value': 'All'},
                    {'label': 'January', 'value': 'January'},
                    {'label': 'February', 'value': 'February'},
                    {'label': 'March', 'value': 'March'},
                    {'label': 'April', 'value': 'April'},
                    {'label': 'May', 'value': 'May'},
                    {'label': 'June', 'value': 'June'},
                    {'label': 'July', 'value': 'July'},
                    {'label': 'August', 'value': 'August'},
                    {'label': 'September', 'value': 'September'},
                    {'label': 'October', 'value': 'October'},
                    {'label': 'November', 'value': 'November'},
                    {'label': 'December', 'value': 'December'}
                ],
                value=month, 
                style={'width': '120px'},
                placeholder='Select a month...',
                clearable=False,
                multi=False)], style={'display': 'flex', 'flex-direction': 'row', 'align-items': 'center', 'justify-content': 'space-between'}),
        
        html.Div([
            html.H4('Hour:',style={'margin-right': '20px'}),
            dcc.Dropdown(
                id='hour_bd',
                options=[{'label':str(i),'value':i} for i in range(24)],
                style={'width': '60px'},
                value=hour, 
                clearable=False,
                placeholder='Select an hour...',
                multi=False)], style={'display': 'flex', 'flex-direction': 'row', 'align-items': 'center','justify-content': 'space-between'}),
        html.Div([
            html.H4('Tolerance:',style={'margin-right': '20px'}),
            dcc.Dropdown(
                id='tolerance_bd',
                options=[{'label':str(i),'value':i} for i in range(13)],
                value=1, 
                style={'width': '60px'},
                clearable=False,
                placeholder='Select a tolerance...',
                multi=False)], style={'display': 'flex', 'flex-direction': 'row', 'align-items': 'center','justify-content': 'space-between'}),
        html.Div([
            html.H4('SFI:'),
            dcc.Input(
                id='sfi_bd',
                type='number',
                style={'width': '70px'},
                placeholder='Enter SFI value...',
                value=sfi)], style={'display': 'flex', 'flex-direction': 'row', 'align-items': 'center','justify-content': 'space-between'}),
        html.Div([
            html.H4('Consider adjacent ranges:',style={'margin-right':'20px'}),
            dcc.Dropdown(
                id='adjacent_ranges_bd',
                options=[{'label':'Yes','value':True},{'label':'No','value':False}],
                value=True,
                multi=False,
                style={'width': '70px'},
                clearable=False)], style={'display': 'flex', 'flex-direction': 'row', 'align-items': 'center','justify-content': 'space-between'}),
        
        html.Div(id='output-dataframe-app2',style={'margin-top': '50px','backgroundColor': 'white'})
    ],style={'margin': 'auto', 'text-align': 'left',"border": "2px solid black","padding": "20px",'backgroundColor': '#FFFFE0'})
    
],style={'display': 'flex', 'flex-direction': 'row', 'align-items': 'center',"justify-content": "center"}) ],style={'margin': 'auto','width':'80%'}),
    
    html.Div([
        
        html.H2("QSO Count Significance vs SFI",style={'text-align': 'center','margin-bottom':'40px'}), 
        
        html.Div([
        html.Div([
            
        html.Div([
            html.H4('Destination:',style={'margin-right': '20px'}),
            dcc.Dropdown(
                id='dest',
                options=destinations,
                style={'width': '280px'},
                value=destinations[0],
                placeholder='Select a destination...',
                clearable=False,
                multi=False)], style={'display': 'flex', 'flex-direction': 'row', 'align-items': 'center', 'justify-content': 'space-between'}),
        
        html.Div([
            html.H4('HF bands:',style={'margin-right': '20px'}),
            dcc.Dropdown(
                id='bands',
                placeholder='Select bands...',
                options=[
                    {'label': '6m', 'value': '6'},
                    {'label': '10m', 'value': '10'},
                    {'label': '12m', 'value': '12'},
                    {'label': '15m', 'value': '15'},
                    {'label': '17m', 'value': '17'},
                    {'label': '20m', 'value': '20'},
                    {'label': '30m', 'value': '30'},
                    {'label': '40m', 'value': '40'},
                    {'label': '60m', 'value': '60'},
                    {'label': '80m', 'value': '80'},
                    {'label': '160m', 'value': '160'}
                ],
                value=['10'],  
                clearable=False,
                multi=True,
                )], style={'display': 'flex', 'flex-direction': 'row', 'justify-content': 'space-between'})
        
        ],style={'margin-right': '20px'}),
        
        
        html.Img(id='plot',style={'width':'70%',"border": "1px solid black"}) ],style={'display': 'flex', 'flex-direction': 'row', 'align-items': 'center','justify-content': 'space-between'})
    ],style={'margin': 'auto', 'text-align': 'left',"border": "2px solid black","padding": "20px",'width':'80%','margin-top':'50px','backgroundColor': '#FFFFE0'}),
    
    html.Div(style={'height': '60px'}),
    
    ],style={'backgroundColor': '#f0f0f0','height': '100%'})


@app.callback(
    Output('output-dataframe-app1', 'children'),
    [Input('band','value'),Input('month','value'),Input('hour','value'),Input('tolerance','value'),Input('sfi','value'),Input('adjacent_ranges','value'),Input('top','value')]
)


def best_dest(band=None, month=None, hour=None, tolerance=1, sfi=None, consider_adjacent_ranges=True, top=10, dataset=qso_dataset): # Recommmends the best candidates for QSOs
    
    if band==None:
        band=input("No band entered! Please enter one of the following bands: 6, 10, 12, 15, 17, 20, 30, 40, 60, 80, 160\n")
    if month==None:
        month=datetime.now().month
    if hour==None:
        hour=datetime.now().hour
    if sfi==None:
        try:
            sfi=get_sfi()
        except:
            sfi=int(input("Failed to fetch current SFI! The SFI information on WM7D's website is probably getting updated. Please enter the SFI value manually:"))
        
    hour=int(hour)
    tolerance=int(tolerance)
    sfi=int(sfi)
    top=int(top)
    consider_adjacent_ranges=bool(consider_adjacent_ranges)
    
    month_names = {
    1: 'January',
    2: 'February',
    3: 'March',
    4: 'April',
    5: 'May',
    6: 'June',
    7: 'July',
    8: 'August',
    9: 'September',
    10: 'October',
    11: 'November',
    12: 'December'}

    if type(month)==int:
        month=month_names[month]

    print('Making destination recommendations based on: \n')
    if consider_adjacent_ranges==True:
        print('    SFI:',sfi,'(considering adjacent ranges)')
    else:
        print('    SFI:',sfi,'(not considering adjacent ranges)')
    print('    Band:',str(band)+'m')
    print('    Month:',month)

    all_hours=set(range(24))
    time_range=time_range_maker(hour,tolerance)
    
    if set(time_range) != all_hours:
        print('    Time (hour):',hour)
        print(f'    Tolerance: ±{tolerance}','hours, so filtering for hours:',time_range)
    else:
        print('    No time filter was applied since the implied time range captures all 24 hours.')

    print('')
    

    df=qso_count_sig_for_dest(month,band,hour,tolerance,dataset)
    
    print(f'Displaying the top {min(top,len(df.index))} QSO candidates...')
    
    print('')
    
    # Getting SFI ranges
    first_dest=list(dataset.keys())[0]
    sfi_ranges=list(dataset[first_dest]['All'].keys())

    for sfi_range in sfi_ranges:
        if sfi > eval(sfi_range)[0] and sfi <= eval(sfi_range)[1]:
            current_range=sfi_range
            break

    if consider_adjacent_ranges==False:
        
        df_return = pd.DataFrame({'QSO Count Significance' : df.loc[current_range].sort_values(ascending=False)}).head(top)
        
    else:
        
        if sfi_ranges.index(current_range)-1>=0:
            range_l=sfi_ranges[sfi_ranges.index(current_range)-1]
        else:
            range_l=current_range

        if sfi_ranges.index(current_range)+1<=len(sfi_ranges)-1:
            range_u=sfi_ranges[sfi_ranges.index(current_range)+1]
        else:
            range_u=current_range

        qso_series=(df.loc[range_l]+df.loc[current_range]+df.loc[range_u])/3 # Averaging results using adjacent ranges should improve accuracy of predictions

        df_return = pd.DataFrame({'QSO Count Significance' : qso_series.sort_values(ascending=False)}).head(top)
    
    return html.Table([
        html.Tr([html.Th("Best Destinations")] + [html.Th(col) for col in df_return.columns]),  # Table header
        *[html.Tr([html.Td(df_return.index[i])] + [html.Td(df_return.iloc[i][col]) for col in df_return.columns]) for i in range(len(df_return))]
    ],style={'border-collapse': 'separate', 'border-spacing': '20px','border': '1px solid black','width': '100%'})

@app.callback(
     Output('output-dataframe-app2', 'children'),
     [Input('month_bd','value'),Input('hour_bd','value'),Input('tolerance_bd','value'),Input('sfi_bd','value'),Input('adjacent_ranges_bd','value')]
)
 
def best_bands(month=None, hour=None, tolerance=1, sfi=None, consider_adjacent_ranges=True, dataset=qso_dataset): # Recommmends the best bands

    if month==None:
        month=datetime.now().month
    if hour==None:
        hour=datetime.now().hour
    if sfi==None:
        try:
            sfi=get_sfi()
        except:
            sfi=int(input('Failed to fetch current SFI! Please enter the SFI value:'))
            
    hour=int(hour)
    tolerance=int(tolerance)
    sfi=int(sfi)
    consider_adjacent_ranges=bool(consider_adjacent_ranges)
        
    month_names = {
    1: 'January',
    2: 'February',
    3: 'March',
    4: 'April',
    5: 'May',
    6: 'June',
    7: 'July',
    8: 'August',
    9: 'September',
    10: 'October',
    11: 'November',
    12: 'December'}

    if type(month)==int:
        month=month_names[month]

    print('Making band recommendations based on: \n')
    if consider_adjacent_ranges==True:
        print('    SFI:',sfi,'(considering adjacent ranges)')
    else:
        print('    SFI:',sfi,'(not considering adjacent ranges)')
    print('    Month:',month)

    all_hours=set(range(24))
    time_range=time_range_maker(hour,tolerance)
    
    if set(time_range) != all_hours:
        print('    Time (hour):',hour)
        print(f'    Tolerance: ±{tolerance}','hours, so filtering for hours:',time_range)
    else:
        print('    No time filter was applied since the the implied time range captures all 24 hours.')

    print('')

    df=qso_count_sig_for_bands(month,hour,tolerance,dataset)
    
    # Getting SFI ranges
    first_dest=list(dataset.keys())[0]
    sfi_ranges=list(dataset[first_dest]['All'].keys())

    for sfi_range in sfi_ranges:
        if sfi > eval(sfi_range)[0] and sfi <= eval(sfi_range)[1]:
            current_range=sfi_range
            break

    if consider_adjacent_ranges==False:
        
        df_return = pd.DataFrame({'QSO Count Significance' : df.loc[current_range].sort_values(ascending=False)})
        
    else:
        
        if sfi_ranges.index(current_range)-1>=0:
            range_l=sfi_ranges[sfi_ranges.index(current_range)-1]
        else:
            range_l=current_range

        if sfi_ranges.index(current_range)+1<=len(sfi_ranges)-1:
            range_u=sfi_ranges[sfi_ranges.index(current_range)+1]
        else:
            range_u=current_range

        qso_series=(df.loc[range_l]+df.loc[current_range]+df.loc[range_u])/3 # Averaging results using adjacent ranges should improve accuracy of predictions

        df_return = pd.DataFrame({'QSO Count Significance' : qso_series.sort_values(ascending=False)})
        
    return html.Table([
        html.Tr([html.Th("Best Bands")] + [html.Th(col) for col in df_return.columns]),  # Table header
        *[html.Tr([html.Td(df_return.index[i])] + [html.Td(df_return.iloc[i][col]) for col in df_return.columns]) for i in range(len(df_return))]
    ],style={'border-collapse': 'separate', 'border-spacing': '20px','border': '1px solid black','width': '100%'})


@app.callback(
     Output('plot', 'src'),
     [Input('dest','value'),Input('bands','value')]
)

def make_plot(dest,bands):
    
    palette = sns.color_palette("husl", 11)
    
    # Fecthing all SFI ranges and bands
    first_dest=list(qso_dataset.keys())[0]
    sfi_ranges=list(qso_dataset[first_dest]['All'].keys())
    del sfi_ranges[1] # We exclude the range (20,40)
    bands_all=list(qso_dataset[first_dest]['All'][sfi_ranges[0]].keys())
    
    plt.figure(figsize=(7, 5))

    plt.ylabel('QSO count significance')
    plt.xlabel('SFI range midpoint')
    plt.title(f'{dest}') 
    
    for band in bands:

        # Making individual lineplots
        sns.lineplot(x=[midpoint(x) for x in sfi_ranges],y=qso_count_sig[dest][band],color=palette[bands_all.index(band)],label=band+'m')
    
    plt.legend(title='Band',loc='upper left',fontsize='small')
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    
    img_str = base64.b64encode(buffer.read()).decode()
    plt.close()  
    
    return f'data:image/png;base64,{img_str}'

@app.callback(
    Output('updated-time', 'children'),
    [Input('update-time', 'n_intervals')])

def update_time(_):
    
    global time
    time=datetime.now()
    
    return f"Current time in Montreal: {time.strftime('%Y-%m-%d %H:%M:%S')}"


@app.callback(
    [Output('sfi', 'value'),Output('sfi_bd', 'value')],
    [Input('update-sfi', 'n_intervals')])

def update_sfi(_):
    global sfi
    sfi=get_sfi()
    return [sfi,sfi]

@app.callback(
    Output('updated-sfi','children'),
    [Input('update-sfi','n_intervals')]
    )

def update_sfi_text(_):
    sfi=get_sfi()
    return f"Current SFI: {sfi} (updated every hour)"

@app.callback(
    [Output('hour', 'value'),Output('hour_bd', 'value')],
    [Input('update-hour', 'n_intervals')])
    
def update_hour(_):
    global hour
    hour=datetime.now().hour
    return [hour,hour]

@app.callback(
    [Output('month', 'value'),Output('month_bd', 'value')],
    [Input('update-month', 'n_intervals')])
    
def update_month(_):
    global month
    month=datetime.now().month
    names={1:'January',2:'February',3:'March',4:'April',5:'May',6:'June',7:'July',8:'August',9:'September',10:'October',11:'November',12:'December'}
    month=names[month]
    return [month,month]
    
if __name__ == '__main__':
    
    app.run_server(host='0.0.0.0',debug=False,port=10000)

