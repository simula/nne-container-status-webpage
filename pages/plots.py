"""Plots now rendered in notebooks – placeholder."""

import dash
from dash import html

dash.register_page(__name__, path="/plots", name="Plots", order=1)

layout = html.Div([html.H2("Plots"), html.P("Placeholder: plots from the notebooks come later.")])
