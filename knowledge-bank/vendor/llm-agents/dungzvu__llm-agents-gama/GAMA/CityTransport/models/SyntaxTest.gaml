/**
* Name: SyntaxTest
* Based on the internal empty template. 
* Author: dung
* Tags: 
*/


model SyntaxTest

species parse_json {
	init {
		
	}
}

experiment e type: gui {
	user_command "Parse JSON Test" {create parse_json;}
}

