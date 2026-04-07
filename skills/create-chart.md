---
name: create-chart
description: Create a B1 chart (bar, line, pie, doughnut, radar, polarArea, scatter) with CLOB-stored configuration and either CLOB data, an existing data source with JMESPath dataConversionExpression, or sample data. Produces a working b1_chart with config CLOB, data source, and optional sample screen.
---

# Create Chart with CLOB Configuration

Guides creation of `b1_chart` objects with `b1_clob`-stored configuration (extendedConfig) and either CLOB-stored chart data or an existing data source with a JMESPath `dataConversionExpression`. Produces a working chart with a config CLOB, a data source, and optional sample screen assembly.

**Reference implementations:**
- `SampleClobChart` screen in the Samples module (bar chart with CLOB config + CLOB data)
- `InvoiceDueDateStatusChartScreen` in the Samples module (bar chart with existing DSO + dataConversionExpression)

---

## Trigger Phrases

Use this skill when the user says any of the following:
- "create a chart"
- "add a chart"
- "create a bar chart" / "create a pie chart" / "create a line chart" (any chart type)
- "chart with CLOB config"
- "add a chart to a screen"
- "create chart visualization"

---

## Phase 1: Gather Requirements

Collect the following from the user before creating any objects. Ask for all items; use sensible defaults where noted.

| Item | Example | Default |
|------|---------|---------|
| Chart type | `bar`, `line`, `pie`, `doughnut`, `radar`, `polarArea`, `scatter` | `bar` |
| Chart object name | `InvoiceSalesChart` | — (required) |
| Config CLOB name | `InvoiceSalesChartConfig` | `{chartName}Config` |
| Module | `Invoicing` | — (required) |
| Data source approach | `clob` / `existing` / `sample` | `clob` |
| Data CLOB name (if clob) | `InvoiceSalesChartData` | `{chartName}Data` |
| Existing data source name (if existing) | `invoiceDSO` | — |
| Data conversion expression (if existing) | JMESPath expression | — (required for existing) |
| DSO filter expression (if existing) | Inline JS for `eventBeforeFetch` | `""` (no filter) |
| Chart title | `"Monthly Sales"` | `""` (no title) |
| Show legend | `true` / `false` | `true` |
| Legend position | `top`, `bottom`, `left`, `right` | `top` (bar/line/radar/scatter), `bottom` (pie/doughnut/polarArea) |
| Show tooltips | `true` / `false` | `true` |
| Create sample screen | `yes` / `no` | `no` |
| Screen name (if yes) | `InvoiceSalesChartScreen` | `{chartName}Screen` |

### Data source approaches

| Key | Description |
|-----|-------------|
| `clob` | Create a new `b1_clob` with chart data provided by the user |
| `existing` | Use an existing `b1_data_source` object — data is transformed to Chart.js format via `dataConversionExpression` |
| `sample` | Use the existing `SampleChartClobData` from the Samples module |

### Data conversion expression (existing DSO)

When using an existing data source, the DSO returns raw tabular rows. A JMESPath `dataConversionExpression` on the chart object transforms these rows into Chart.js format `{ labels, datasets }` on the frontend.

A custom `group_by(array, 'fieldName')` function is available that groups array elements by a field value and returns an array of arrays.

**Common patterns:**

Group by a single field and count:
```
{labels: group_by(@, 'status')[*][0].status, datasets: [{label: 'Count', data: group_by(@, 'status')[*].length(@)}]}
```

Group by a single field and sum a value field:
```
{labels: group_by(@, 'category')[*][0].category, datasets: [{label: 'Total', data: group_by(@, 'category')[*][*].amount | [*].sum(@)}]}
```

Simple field mapping (no aggregation, data already in the right shape):
```
{labels: [*].month, datasets: [{label: 'Revenue', data: [*].revenue}]}
```

### DSO filtering via inline client logic

When using an existing data source, you can filter rows via an inline `eventBeforeFetch` attribute on the DSO instance. This is inline JavaScript (no `#.` prefix, no separate client logic file).

**Examples:**
```
eventSource.addFilter('status', 'ne', 'draft')
```
```
eventSource.addFilter('dueDate', 'ge', '2026-01-01')
```

---

## Phase 2: Create Config CLOB

Create a `b1_clob` object containing the Chart.js extendedConfig JSON.

1. Select the default config template for the chosen chart type (see [Default Config Templates](#default-config-templates) below)
2. Apply user preferences:
   - Set `plugins.title.display` to `true` and `plugins.title.text` to the user's title (if provided)
   - Set `plugins.legend.display` and `plugins.legend.position` per user input
   - Set `plugins.tooltip.enabled` per user input
3. Stringify the config JSON
4. Call `mcp__B1_Blueprint__create_blueprint`:

```
objectTypeName: "b1_clob"
objectName: {configClobName}
moduleName: {module}
objectDescription: "{chartName} extended config"
attributes:
  content: {stringified config JSON}
  contentType: "json"
```

---

## Phase 3: Create Data CLOB (conditional)

**Skip this phase if** data source approach is `existing` or `sample`.

Collect labels and dataset values from the user, then build the data JSON.

### Standard data format (bar, line, pie, doughnut, radar, polarArea)

```json
[{
  "labels": ["January", "February", "March", "April", "May", "June", "July"],
  "datasets": [
    {
      "label": "Sales Q1",
      "data": [65, 59, 80, 81, 56, 55, 40]
    },
    {
      "label": "Sales Q2",
      "data": [28, 48, 40, 19, 86, 27, 90]
    }
  ]
}]
```

### Scatter data format

Scatter charts use `{ x, y }` point objects instead of flat number arrays:

```json
[{
  "labels": [],
  "datasets": [
    {
      "label": "Measurements",
      "data": [
        { "x": 10, "y": 20 },
        { "x": 15, "y": 10 },
        { "x": 25, "y": 30 }
      ]
    }
  ]
}]
```

Call `mcp__B1_Blueprint__create_blueprint`:

```
objectTypeName: "b1_clob"
objectName: {dataClobName}
moduleName: {module}
objectDescription: "{chartName} chart data"
attributes:
  content: {stringified data JSON}
  contentType: "json"
```

---

## Phase 4: Create Chart Object

Create the `b1_chart` object with `extendedConfig` pointing to the config CLOB endpoint.

Call `mcp__B1_Blueprint__create_blueprint`:

### For `clob` or `sample` data source approach:

```
objectTypeName: "b1_chart"
objectName: {chartName}
moduleName: {module}
objectDescription: {user description or chartName}
attributes:
  extendedConfig: "/service/app/data/clob/{configClobName}"
```

### For `existing` data source approach:

```
objectTypeName: "b1_chart"
objectName: {chartName}
moduleName: {module}
objectDescription: {user description or chartName}
attributes:
  extendedConfig: "/service/app/data/clob/{configClobName}"
  dataConversionExpression: {JMESPath expression}
```

**Important:** The `extendedConfig` value must be the full CLOB endpoint path with the `/service/app/` prefix. Do NOT use static file paths like `/resources/chart/bar.json`.

---

## Phase 5: Create Sample Screen (optional)

**Skip this phase unless** the user explicitly requested a sample screen.

Assemble a screen following the appropriate pattern. Use `mcp__B1_Blueprint__create_blueprint` to create the screen with all instances and links in a single call.

### Screen structure for `clob` or `sample` data source

```
b1_screen "{screenName}"
  attributes:
    title: "{chart title or chartName}"
  instances:
    1. b1_data_source "{chartName}DSO"
       objectMasterGuid: "bb01982b-83bb-af8b-da14-5dd5f8b65b1a"
       attributes:
         subtype: "MockupCollection"
         resourceName: "/service/app/data/clob/{dataClobName}"
    2. b1_panel "a"
       layoutPosition: "a"
       objectMasterGuid: "31572117-2fe3-4262-ba03-20a74c6b59ca"
       instances:
         3. b1_chart "{chartName}"
            objectMasterGuid: {chart objectMasterGuid from Phase 4}
            attributes:
              extendedConfig: "/service/app/data/clob/{configClobName}"
  links:
    - DATA link from DSO instance to chart instance
      linkTypeGuid: "d37727fb-24ff-7ea3-0e14-a5d9d8526f38"
      linkName: "Data"
```

### Screen structure for `existing` data source

```
b1_screen "{screenName}"
  attributes:
    title: "{chart title or chartName}"
  instances:
    1. b1_data_source "{chartName}DSO"
       objectMasterGuid: {existing DSO objectMasterGuid}
       attributes:
         eventBeforeFetch: {inline filter JS or empty}
    2. b1_panel "a"
       layoutPosition: "a"
       objectMasterGuid: "31572117-2fe3-4262-ba03-20a74c6b59ca"
       instances:
         3. b1_chart "{chartName}"
            objectMasterGuid: {chart objectMasterGuid from Phase 4}
            attributes:
              extendedConfig: "/service/app/data/clob/{configClobName}"
              dataConversionExpression: {JMESPath expression}
  links:
    - DATA link from DSO instance to chart instance
      linkTypeGuid: "d37727fb-24ff-7ea3-0e14-a5d9d8526f38"
      linkName: "Data"
```

**To get the existing DSO's objectMasterGuid**, call `mcp__B1_Blueprint__get_object` with `detail: "full"` on the data source name.

### Data source resolution

| Data source approach | DSO instance setup |
|---------------------|----------------------|
| `clob` | objectMasterGuid: `bb01982b-83bb-af8b-da14-5dd5f8b65b1a`, subtype: `MockupCollection`, resourceName: `/service/app/data/clob/{dataClobName}` |
| `sample` | objectMasterGuid: `bb01982b-83bb-af8b-da14-5dd5f8b65b1a`, subtype: `MockupCollection`, resourceName: `/service/app/data/clob/SampleChartClobData` |
| `existing` | objectMasterGuid: from `mcp__B1_Blueprint__get_object` on the existing DSO, optional `eventBeforeFetch` for filtering |

---

## Phase 6: Preview & Verify

If a screen was created in Phase 5:
- Call `mcp__B1_Blueprint__preview_screen` with the screen name to show the result

If no screen was created:
- Explain to the user how to embed the chart into an existing screen:
  1. Add a `b1_data_source` instance (CLOB-based or existing DSO)
  2. Add a `b1_panel` instance at a layout position
  3. Add the chart as an instance inside the panel
  4. Create a DATA link from the data source to the chart

---

## Default Config Templates

### Bar

```json
{
  "type": "bar",
  "options": {
    "responsive": true,
    "maintainAspectRatio": false,
    "aspectRatio": 0.6,
    "plugins": {
      "legend": { "display": true, "position": "top", "labels": { "usePointStyle": true } },
      "tooltip": { "enabled": true },
      "title": { "display": false, "text": "" }
    },
    "scales": {
      "x": { "ticks": { "font": { "weight": 500 } }, "grid": { "display": false, "drawBorder": false } },
      "y": { "ticks": {}, "grid": { "drawBorder": false } }
    }
  }
}
```

### Line

```json
{
  "type": "line",
  "options": {
    "responsive": true,
    "maintainAspectRatio": false,
    "aspectRatio": 0.6,
    "plugins": {
      "legend": { "display": true, "position": "top", "labels": { "usePointStyle": true } },
      "tooltip": { "enabled": true },
      "title": { "display": false, "text": "" }
    },
    "scales": {
      "x": { "ticks": { "font": { "weight": 500 } }, "grid": { "display": false, "drawBorder": false } },
      "y": { "ticks": {}, "grid": { "drawBorder": false } }
    }
  }
}
```

> **Tip:** For smooth curves, add `"tension": 0.4` to each dataset when creating chart data.

### Pie

```json
{
  "type": "pie",
  "options": {
    "responsive": true,
    "maintainAspectRatio": false,
    "plugins": {
      "legend": { "display": true, "position": "bottom", "labels": { "usePointStyle": true, "padding": 20 } },
      "tooltip": { "enabled": true },
      "title": { "display": false, "text": "" }
    }
  }
}
```

### Doughnut

```json
{
  "type": "doughnut",
  "options": {
    "responsive": true,
    "maintainAspectRatio": false,
    "plugins": {
      "legend": { "display": true, "position": "bottom", "labels": { "usePointStyle": true, "padding": 20 } },
      "tooltip": { "enabled": true },
      "title": { "display": false, "text": "" }
    }
  }
}
```

### Radar

```json
{
  "type": "radar",
  "options": {
    "responsive": true,
    "maintainAspectRatio": false,
    "plugins": {
      "legend": { "display": true, "position": "top", "labels": { "usePointStyle": true, "padding": 20 } },
      "tooltip": { "enabled": true },
      "title": { "display": false, "text": "" }
    },
    "scales": {
      "r": { "beginAtZero": true, "ticks": {}, "grid": {}, "pointLabels": {} }
    }
  }
}
```

### Polar Area

```json
{
  "type": "polarArea",
  "options": {
    "responsive": true,
    "maintainAspectRatio": false,
    "plugins": {
      "legend": { "display": true, "position": "bottom", "labels": { "usePointStyle": true, "padding": 20 } },
      "tooltip": { "enabled": true },
      "title": { "display": false, "text": "" }
    },
    "scales": {
      "r": { "ticks": {}, "grid": {} }
    }
  }
}
```

### Scatter

```json
{
  "type": "scatter",
  "options": {
    "responsive": true,
    "maintainAspectRatio": false,
    "aspectRatio": 0.6,
    "plugins": {
      "legend": { "display": true, "position": "top", "labels": { "usePointStyle": true } },
      "tooltip": { "enabled": true },
      "title": { "display": false, "text": "" }
    },
    "scales": {
      "x": { "ticks": { "font": { "weight": 500 } }, "grid": { "display": false, "drawBorder": false } },
      "y": { "ticks": {}, "grid": { "drawBorder": false } }
    }
  }
}
```

---

## Important Rules

1. **Always use CLOB for extendedConfig** — Store chart configuration in a `b1_clob` object and set `extendedConfig` to the CLOB endpoint path. Do not inline large JSON directly in the attribute.
2. **Resource path format** — Both `extendedConfig` and data source `resourceName` must use the full proxy path: `/service/app/data/clob/{clobName}`.
3. **DATA link is required** — A chart must have a DATA link from a data source to receive data. Without it, the chart renders empty.
4. **Data must be wrapped in an array** — CLOB chart data format is `[{ "labels": [...], "datasets": [...] }]`. The outer array is required.
5. **No scales for pie/doughnut** — Pie and doughnut charts do NOT use `scales` in their config. Do not include `scales` for these types.
6. **Scatter data points** — Scatter chart datasets use `{ x, y }` point objects, not flat number arrays.
7. **Never modify sample objects** — `SampleBarChart`, `SampleChartBarExtendedConfig`, `SampleChartClobData`, and `SampleClobChart` are reference implementations. Do not alter them.
8. **Always use B1 MCP** — Use `mcp__B1_Blueprint__create_blueprint` and `mcp__B1_Blueprint__patch_blueprint` for all blueprint operations. Never edit JSON files directly.
9. **Naming conventions** — Config CLOB: `{ChartName}Config`, Data CLOB: `{ChartName}Data`, DSO instance: `{ChartName}DSO`, Screen: `{ChartName}Screen`.
10. **dataConversionExpression is for existing DSOs only** — Only set `dataConversionExpression` when the data source returns raw tabular rows. CLOB and sample data sources already provide Chart.js format and do not need it.
11. **Inline client logic for DSO filtering** — When using an existing DSO, set `eventBeforeFetch` directly on the DSO instance attribute as inline JavaScript. Do NOT create separate client logic files.
12. **group_by syntax** — The custom `group_by` function takes a string field name: `group_by(@, 'fieldName')`. Do NOT use expression references like `&fieldName`.

---

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| Chart renders empty / no data | Missing DATA link between data source and chart | Add a DATA link (linkTypeGuid `d37727fb-24ff-7ea3-0e14-a5d9d8526f38`) from the DSO instance to the chart instance |
| Chart shows wrong type | Incorrect `type` in config CLOB | Update the `content` attribute of the config CLOB with the correct `type` value |
| CLOB returns 404 | Object name mismatch | Verify the `b1_clob` object exists with `mcp__B1_Blueprint__get_object`. Check `objectName` matches the path segment |
| CLOB returns 400 | Invalid JSON in `content` or unsupported `contentType` | Validate `content` is well-formed JSON. Ensure `contentType` is `"json"` |
| Config not applied | Wrong `extendedConfig` path | Verify path starts with `/service/app/data/clob/` (not `/resources/chart/`) |
| Chart distorted / wrong size | Missing responsive config | Set `responsive: true` and `maintainAspectRatio: false` in config options. Adjust `aspectRatio` |
| Legend not showing | `legend.display` is false | Set `plugins.legend.display` to `true` in the config CLOB content |
| Tooltips not showing | `tooltip.enabled` is false | Set `plugins.tooltip.enabled` to `true` in the config CLOB content |
| dataConversionExpression not working | Expression syntax error or wrong function | Check browser console for `[jmespath] Transformation failed` warnings. Verify `group_by` uses string field name syntax |
| Chart empty with existing DSO | DSO returns no records | Check that `eventBeforeFetch` filter isn't too restrictive. Verify DSO `resourceName` is correct |

---

## Examples

### Example 1: Bar Chart with CLOB Config + CLOB Data

This is the reference implementation in the Samples module:

- **Config CLOB:** `SampleChartBarExtendedConfig` — bar chart options with scales, legend, tooltips
- **Data CLOB:** `SampleChartClobData` — 7 months of sales data with 2 datasets
- **Chart object:** `SampleBarChart` — references config via `extendedConfig`
- **Screen:** `SampleClobChart` — assembles DSO, panel, chart, and DATA link

### Example 2: Bar Chart with Existing DSO + dataConversionExpression

This example uses a live database data source with JMESPath transformation:

- **Config CLOB:** `InvoiceDueDateStatusChartConfig` — bar chart options with title "Invoices by Due Date & Status"
- **Existing DSO:** `invoiceDSO` — fetches invoice rows from PostgreSQL
- **Chart object:** `InvoiceDueDateStatusChart` — references config via `extendedConfig`, transforms data via `dataConversionExpression`:
  ```
  {labels: group_by(@, 'status')[*][0].status, datasets: [{label: 'Invoices by Status', data: group_by(@, 'status')[*].length(@)}]}
  ```
- **Screen:** `InvoiceDueDateStatusChartScreen` — uses `invoiceDSO` instance with inline `eventBeforeFetch: "eventSource.addFilter('status', 'ne', 'draft')"` to exclude drafts
- **DATA link** from DSO to chart triggers the transformation pipeline

### Example 3: Embedding a Chart in an Existing Screen

To add a chart to an existing screen, use `mcp__B1_Blueprint__patch_blueprint` to:

1. Add a `b1_data_source` instance (CLOB-based with `subtype: "MockupCollection"` and `resourceName`, or an existing DSO with optional `eventBeforeFetch`)
2. Add a `b1_panel` instance at the desired layout position
3. Add the chart object as an instance inside the panel, setting `extendedConfig` to the config CLOB path (and `dataConversionExpression` if using an existing DSO)
4. Add a DATA link from the data source instance to the chart instance

---

## Reference

| Purpose | Resource |
|---------|----------|
| Sample CLOB chart screen | `SampleClobChart` (Samples module) |
| Sample existing DSO chart screen | `InvoiceDueDateStatusChartScreen` (Samples module) |
| Sample config CLOB | `SampleChartBarExtendedConfig` (Samples module) |
| Sample data CLOB | `SampleChartClobData` (Samples module) |
| Sample chart objects | `SampleBarChart`, `SamplePieChart`, `SamplePolarChart`, `SampleRadarChart` (Samples module) |
| Chart with dataConversionExpression | `InvoiceDueDateStatusChart` (Samples module) |
| Static config templates | `src/web-framework/layer/public/resources/chart/*.json` |
| CLOB data source docs | `src/cli/knowledge/architecture_info/clob-data-sources.md` |
| Chart object type docs | `src/web-docs/docs/object-types/b1_chart.md` |
| CLOB object type docs | `src/web-docs/docs/object-types/b1_clob.md` |
| JMESPath utility | `src/web-core/src/utils/jmespath.ts` |
