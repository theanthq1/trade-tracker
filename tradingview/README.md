# Trade chart assets

The app currently renders the trade chart with its local canvas renderer, so
no external chart package is required. If an authorized TradingView package is
available, it can still be placed here for a future renderer:

```text
tradingview/charting_library/charting_library.standalone.js
tradingview/charting_library/...
tradingview/datafeeds/udf/dist/bundle.js
```

The application hosts these files locally and connects the built-in
`UDFCompatibleDatafeed` adapter to its local `/udf` endpoints. The local UDF
server requests one-minute historical stock bars from Yahoo Finance and never
exposes a provider credential to the browser. The library package itself is
not generated or copied into this repository.
