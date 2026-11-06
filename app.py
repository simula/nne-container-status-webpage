"""NNE container status webpage: Dash app (Dash Pages) with the nne-viz look – header, navigation, clock, footer.

Development:  python app.py               (http://localhost:8050, debug mode)
Production:   gunicorn app:server         (see Dockerfile)
"""

import dash
from dash import ALL, Dash, Input, Output, dcc, html

app = Dash(__name__, use_pages=True, title="NorNet edge – container status")
server = app.server


def layout():
    """Page frame as nne-viz web/src/components/Base.tsx: header, view, footer."""
    pages = dash.page_registry.values()
    nav = [dcc.Link(page["name"], href=page["relative_path"], id={"type": "nav", "index": page["relative_path"]},
                    className="header-button") for page in pages]
    clock = html.Div([html.Span("Norway datetime :"), html.Span(id="clock-date"), html.Span(id="clock-time")],
                     className="clock")
    return html.Div(className="base", children=[
        dcc.Location(id="url"),
        dcc.Interval(id="clock-tick", interval=1000),
        html.Header(className="header", children=[
            html.Div(className="header-start", children=[
                html.A(html.Img(src=dash.get_asset_url("nornet.png"), alt="Nornet logo", className="logo"),
                       href="https://www.nntb.no/", target="_blank"),
                html.H1("NorNet edge", className="header-text"),
            ]),
            html.Div(nav + [clock], className="header-end"),
        ]),
        html.Main(dash.page_container, className="view"),
        html.Footer(className="footer", children=[
            html.Span("© Simula Research Laboratory"),
            html.Div(html.Img(src=dash.get_asset_url("simulamet.svg"), alt="SimulaMet"), className="footer-end"),
        ]),
    ])


app.layout = layout


@dash.callback(Output({"type": "nav", "index": ALL}, "className"), Input("url", "pathname"))
def select_nav(pathname):
    return ["header-button selected" if page["relative_path"] == pathname else "header-button"
            for page in dash.page_registry.values()]


# Clock in the browser (as nne-viz Clock.tsx), no request to the server
app.clientside_callback(
    """(tick) => {
        const now = new Date(), zone = {timeZone: "Europe/Oslo"};
        return [now.toLocaleDateString("en-GB", zone), now.toLocaleTimeString("en-GB", {...zone, hour12: false})];
    }""",
    Output("clock-date", "children"), Output("clock-time", "children"), Input("clock-tick", "n_intervals"))


if __name__ == "__main__":
    app.run(debug=True)
