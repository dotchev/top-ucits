# Yahoo symbol lookup

1. search yahoo for <ticker>.DE, pick first listing with symbol <ticker>.DE
2. search yahoo for isin, pick .DE listing
3. get the first listing from the last search and get its longname or shortname and use it to search yahoo, select the listings with matching longname or shortname and pick the listing with matching extension
4. pick the listing with matching extension from the result from step 2
5. pick first listing from results from step 2
6. search yahoo for name, pick the listing with matching extension

when searching yahoo consider only listings with quoteType ETF or EQUITY
when matching listing extensions select based on this priority list .DE > .MI > .AS > .PA

## Output

CSV output columns:
- isin - copy from source
- symbol - Yahoo symbol from lookup result
- name - Yahoo name from lookup result

## Symbol cache

Use yahoo-symbol-cache.csv (see its structure) as Yahoo symbol cache.
If the symbol is already present there, use it instead of calling Yahoo API.
If not, perform yahoo symbol lookup and save the result in the cache.
Save the cache on each update so if the script is interrupted, the cache updates are not lost.