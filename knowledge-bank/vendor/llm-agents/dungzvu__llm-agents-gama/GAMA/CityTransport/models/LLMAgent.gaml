/**
* Name: LLMAgent
* Based on the internal empty template. 
* Author: dung
* Tags: 
*/


model LLMAgent

import "Settings.gaml"

import "Inhabitant.gaml"

global {
	int http_port <- 8002;
	string http_url <- "http://localhost";
	
	int mqtt_port <- 1883;
	string mqtt_url <- "localhost";
	string mqtt_action_topic <- "action/data";
    string mqtt_observation_topic <- "observation/data";
	
	init {
		create llm_agent_sync number: 1 {
			do connect to: http_url protocol: "http" port: http_port raw: true;
		}
		
		create llm_agent_async number: 1 {
			do connect protocol: "websocket_server" port: 3001 with_name: name raw: true;
		}
	}
}

species llm_agent_sync skills:[network] {
	reflex init when: cycle = 1 {
		write "Init population -> LLM, timestamp: " + CURRENT_TIMESTAMP;	

		do send to: "/init" contents: [
			"POST",
			to_json([
				"timestamp"::CURRENT_TIMESTAMP
			]),
			["Content-Type"::"application/json"]
		];
	}
	
	reflex sync when: every(15#mn) and cycle > 1 {
		list<unknown> idle_people <- [];
		if every(60#mn) {
			loop p over: inhabitant where (each.is_idle) {
				point ploc <- point(p.location CRS_transform(POPULATION_CRS));
				idle_people << [
					"person_id"::p.person_id,
					"location"::[
						"lon"::ploc.x,
				    	"lat"::ploc.y
					]	
				];
			}
		}
		do send to: "/sync" contents: [
			"POST",
			to_json([
				"timestamp"::CURRENT_TIMESTAMP,
				"idle_people"::idle_people
			]),
			["Content-Type"::"application/json"]
		];
	}
	
	
	reflex get_message {
		loop while:has_more_message()
		{
			message mess <- fetch_message();
			string jsonBody <- map(mess.contents)["BODY"];
			map<string, unknown> json <- from_json(jsonBody);
			if bool(json["success"]) != true {
				write "[ERROR] Got error message: " + string(json);
				continue;
			}
			string messageType <- json["message_type"];
			if messageType = "ag_world_init" {
				map<string, unknown> data <- json["data"];
				list<map<string, unknown>> people <- data["people"];
				loop p over: people {
					float lon <- float(p["location"]["lon"]);
					float lat <- float(p["location"]["lat"]);
					point plocation <- point(to_GAMA_CRS({lon, lat}, POPULATION_CRS));
					create inhabitant with: [
						route_vehicle_map::ROUTE_VEHICLE_MAP,
						person_name::string(p["name"]),
						person_id::string(p["person_id"]),
//						age::int(p["age"]),
						location::plocation,
						is_llm_based::bool(p["is_llm_based"])
					] {
						INHABITANT_MAP[self.person_id] <- self;
					}
				}
			} 
		}
		
	}
}


species llm_agent_async skills:[network] { 
	string send_to;
	
//	reflex send when: send_to != nil and every(2#mn) {
//		write "Sending...";
//		do send to: send_to contents: name + " at " + cycle + " sent to server_group a message";
//	}

	reflex submit_obseration when: send_to !=nil and every(5#mn) {
		loop p over: (inhabitant where (length(each.OB_LIST) > 0)) {
			list<map<string, unknown>> ob_list <- p.OB_LIST;
			p.OB_LIST <- [];
			loop ob over: ob_list {
				point ploc <- point(p.location CRS_transform(POPULATION_CRS));
				map<string, unknown> ob_payload <- [
					"person_id"::p.person_id,
					"activity_id"::ob["activity_id"],
					"timestamp"::CURRENT_TIMESTAMP,
					"location"::[
						"lon"::ploc.x,
			    		"lat"::ploc.y
					],
				    "env_ob_code"::string(ob["type"]),
				    "data"::ob
				];
				string payload <- to_json([
					"topic"::"observation/data",
					"payload"::ob_payload
				]);
				do send to: send_to contents: payload;
				write "Send observation of " + p.person_id + ": " + ob;
			}
		}
	}
	   	
	reflex get_message when: has_more_message() {
		loop while:has_more_message()
		{
			message mess <- fetch_message();
			send_to <- mess.sender;
			write "mess.contents " + map(mess.contents);
			string action_data_json <- map(mess.contents)["contents"];
			map<string, unknown> payload_data <- from_json(action_data_json);
			string topic <- payload_data["topic"];
			if topic != "action/data" {
				continue;
			}
			map<string, unknown> action_data <- payload_data["payload"];
			

			string person_id <- action_data["person_id"];
			map<string, unknown> data <- action_data["action"];
			inhabitant person <- INHABITANT_MAP[person_id];
			if person != nil {
				write "DATA: "+ data;
				ask person {
					self.moving_id <- string(data["move_id"]);
					self.activity_id <- string(data["for_activity"]["id"]);
					self.purpose <- string(data["purpose"]);
					self.expected_arrive_at <- int(data["expected_arrive_at"]);
					int prepare_before_seconds <- int(data["prepare_before_seconds"]);
					self.schedule_at <- self.expected_arrive_at - prepare_before_seconds;
//						self.moving_description <- string(data["description"]);
					do passenger_set_plan(
						data["target_location"],
						data["plan"]["legs"],
						data
					);
				}	
			} else {
				 write "Not found the person: " + person_id;
			}
			
		}
		
	}
}

species llm_agent_test skills:[network] {    	
	reflex get_message {
		loop while:has_more_message()
		{
			message mess <- fetch_message();
			write "mess " + mess;
		}
		
	}
}

