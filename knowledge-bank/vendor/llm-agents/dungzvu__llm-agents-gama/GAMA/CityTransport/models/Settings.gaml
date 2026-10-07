/**
* Name: MapData
* Based on the internal empty template. 
* Author: dung
* Tags: 
*/


model Settings

global {
	// feature toggle
	bool ft_public_transport_eval <- false;
	bool ft_evaluate_modality_choices <- false;
	
	string diff_arrival_time_file -> "../results/diff_arrival_time.csv";
	string evaluate_modality_choices_file -> "../results/evaluate_modality_choices.csv";
	string evaluate_density_file -> "../results/evaluate_density.csv";
	
	int LLMAGENT_QUERY_MOVE_BATCH_SIZE <- 200;
	
	// TODO: uncomment this line to enable fixed_date GTFS lookup 
//	 date GTFS_FIXED_DATE <- date([2025,3,5,0,0,0]);
	date GTFS_FIXED_DATE <- nil;
	
	// config
	date starting_date <- date([2025,3,3,3,30,0]);
	
	// Global helper variables
	date UTC_START_DATE <- date([1970,1,1,0,0,0]);
	int CURRENT_TIMESTAMP -> int(current_date - UTC_START_DATE);
	int SECONDS_IN_24H <- 24*3600;
	int CURRENT_TIMESTAMP_24H -> (int(current_date - UTC_START_DATE)) mod SECONDS_IN_24H;
	
	// Shape
	file routes0_shape_file <- shape_file("../includes/routes.shp");
	file stops0_shape_file <- shape_file("../includes/stops.shp");
	file trip_info_file <- json_file("../includes/trip_info.json");
	map<string, unknown> TRIP_INFO <- trip_info_file.contents;
	list<map<string, unknown>> TRIP_LIST <- TRIP_INFO["trip_list"];
	
	geometry shape <- envelope(routes0_shape_file);
	
	map<float, float> ROUTE_DISPLAY_WIDTH <- [
		0::20, // T1: 
		1::30, // Metro A, B
		3::3, // Bus
		6::8 // Teleo
	];
	
	map<float, int> VEHICLE_MAX_CAPACITY <- [
		0::200,
		1::200,
		3::100,
		6::1500
	];
	
	map<string, string> PURPOSE_ICON_MAP <- [
		"home"::"🏠",
		"work"::"🏢",
		"education"::"🏢",
		"shop"::"🛒",
		"leisure"::"🎵",
		"other"::"",
		"__MOVING__"::"🚌",
		"__WALKING__"::"🚶"
	];
	
//	string POPULATION_CRS <- "EPSG:2154";
	string POPULATION_CRS <- "EPSG:4326";
}

