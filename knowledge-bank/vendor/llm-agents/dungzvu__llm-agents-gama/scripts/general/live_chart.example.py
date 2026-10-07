import dash
from dash import dcc, html
from dash.dependencies import Output, Input
import random
from collections import deque
import plotly.graph_objs as go

app = dash.Dash(__name__)
x = deque(maxlen=100)
y = deque(maxlen=100)

x.append(0)
y.append(1)

app.layout = html.Div([
    dcc.Graph(id='live-graph'),
    dcc.Interval(id='interval', interval=1000, n_intervals=0)
])

@app.callback(Output('live-graph', 'figure'), Input('interval', 'n_intervals'))
def update(n):
    x.append(x[-1] + 1)
    y.append(y[-1] + random.uniform(-0.5, 0.5))

    return {
        'data': [go.Scatter(x=list(x), y=list(y), mode='lines+markers')],
        'layout': go.Layout(xaxis=dict(range=[min(x), max(x)]),
                            yaxis=dict(range=[min(y)-1, max(y)+1]))
    }

app.run(debug=True)
