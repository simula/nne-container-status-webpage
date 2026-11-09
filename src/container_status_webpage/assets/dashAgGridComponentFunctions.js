/*
 * Custom AG Grid components of dash-ag-grid, loaded by Dash from assets/.
 *
 * ThreadTable: tooltip of a container cell of the colour grid (components/grid.py hover):
 * props.value = {title, rows: [{thread, state, colour, version, up, seen, ago, starts, orphan}]}.
 * Built from React elements, no HTML strings.
 */

var dagcomponentfuncs = (window.dashAgGridComponentFunctions =
  window.dashAgGridComponentFunctions || {});

dagcomponentfuncs.ThreadTable = function (props) {
  var e = React.createElement;
  var tip = props.value;
  var columns = [
    ["thread", "Thread"],
    ["state", "State"],
    ["version", "Version"],
    ["up", "Up"],
    ["seen", "Last seen (UTC)"],
    ["ago", "Ago"],
    ["starts", "Starts 24 h / 7 d"],
    ["restarts", "Receiver restarts"],
  ];

  function cell(row, key) {
    if (key === "state") {
      return e("td", { key: key }, e("i", { style: { backgroundColor: row.colour } }), row.state);
    }
    return e("td", { key: key }, key === "thread" && row.orphan ? "⚠ " + row.thread : row[key]);
  }

  return e(
    "div",
    { className: "thread-tip" },
    e("div", { className: "thread-tip-title" }, tip.title),
    e(
      "table",
      null,
      e(
        "thead",
        null,
        e("tr", null, columns.map(function (column) {
          return e("th", { key: column[0] }, column[1]);
        }))
      ),
      e(
        "tbody",
        null,
        tip.rows.map(function (row) {
          return e(
            "tr",
            { key: row.thread, className: row.orphan ? "orphan" : "" },
            columns.map(function (column) {
              return cell(row, column[0]);
            })
          );
        })
      )
    )
  );
};
