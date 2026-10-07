# SMKlog Parcel Shipping Rates

Five tools on one remote server, no credentials:

1. `get_parcel_quote` first. Give the item in plain words (brand and model help),
   the US origin ZIP, and the destination: a US ZIP, or a postal code plus
   `to_country_code` for CA, GB, DE or AU. You get the estimated packed box,
   live carrier rates with transit days, and a `quote_id`.
2. `create_checkout_link` with that `quote_id` to turn the chosen rate into a
   hosted checkout page for the human. Keep the returned `session_id`.
3. `get_checkout_status` with the `session_id` to learn when the human has
   paid and when the label exists; it returns the tracking number at
   `label_ready`.
4. `track_parcel` with a tracking number for scan events on SMKlog labels.
5. `get_price_index` for the monthly reference basket of US parcel prices.

Origins are always in the United States. Quotes are limited per hour per
caller; do not loop on the same parcel. Prices are all-in customer amounts.
