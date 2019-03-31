\pset format unaligned
\pset fieldsep ,
SELECT calendar.service_id, stops.stop_name, stops.stop_id, stop_times.departure_time FROM stop_times LEFT OUTER JOIN stops USING (stop_id) LEFT OUTER JOIN trips USING (trip_id) LEFT OUTER JOIN calendar USING (service_id) ORDER BY calendar.service_id, stops.stop_id, stop_times.departure_time;
