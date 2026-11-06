"""Container status dashboard – placeholder until the dashboard step."""

import dash
from dash import html

dash.register_page(__name__, path="/", name="Containers", order=0)

layout = html.Div([html.H2("Container status"), html.P("Placeholder: the dashboard comes in the next step.")])
