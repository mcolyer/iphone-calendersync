#include <libiphone/libiphone.h>
#include <plist/plist.h>
#include <stdlib.h>
#include <string.h>

void debug_response(plist_t response){
	char *buffer = NULL;
	uint32_t len = 0;

	plist_to_xml(response, &buffer, &len);
	printf("%s\n", buffer);
}

int main(){
	iphone_device_t device = NULL;
	iphone_lckd_client_t lckd = NULL;
	iphone_msync_client_t msync = NULL;
	int res = 0;

	if ( IPHONE_E_SUCCESS == iphone_get_device( &(device) ) && device ) {
	  if (IPHONE_E_SUCCESS == iphone_lckd_new_client( device, &(lckd)) && lckd ) {
	
	    int port = 0;
	    if (IPHONE_E_SUCCESS == iphone_lckd_start_service ( lckd, "com.apple.mobilesync", &port ) && port != 0 ) {
	      if (IPHONE_E_SUCCESS == iphone_msync_new_client ( device, 3458, port, &(msync)) && msync )
	        res = 1;
	    }
	  }
	}

	if (!res)
	  goto error;

	printf("Succesfully connected\n");

	// Create Initialization Message
	plist_t array = NULL;
	iphone_error_t ret = IPHONE_E_UNKNOWN_ERROR;

	array = plist_new_array();
	plist_add_sub_string_el(array, "SDMessageSyncDataClassWithDevice");
	plist_add_sub_string_el(array, "com.apple.Calendars");

	// Force slow timestamp for now
	char *timestamp = NULL;
	timestamp = strdup("---");

	// This should be the current time but for now it is the right format
	char* new_timestamp = strdup("2009-01-06 08:42:58 +0100");

	plist_add_sub_string_el(array, timestamp);
	plist_add_sub_string_el(array, new_timestamp);

	plist_add_sub_uint_el(array, 104);
	plist_add_sub_string_el(array, "___EmptyParameterString___");

	ret = iphone_msync_send(msync, array);
	plist_free(array);
	array = NULL;

	// Get Response
	ret = iphone_msync_recv(msync, &array);
	debug_response(array);
	
	// Ask for the changes
	array = plist_new_array();
	//plist_add_sub_string_el(array, "SDMessageGetChangesFromDevice");
	plist_add_sub_string_el(array, "SDMessageGetAllRecordsFromDevice");
	plist_add_sub_string_el(array, "com.apple.Calendars");
	
	// Send "ask for changes"
	ret = iphone_msync_send(msync, array);
	plist_free(array);
	array = NULL;

	// Get Response - Returns a list of the calendars
	ret = iphone_msync_recv(msync, &array);
	debug_response(array);

	// Acknowledge the response - Events
	array = plist_new_array();
	plist_add_sub_string_el(array, "SDMessageAcknowledgeChangesFromDevice");
	plist_add_sub_string_el(array, "com.apple.Calendars");
	
	// Send acknowledgement
	ret = iphone_msync_send(msync, array);
	plist_free(array);
	array = NULL;

	// Get Response - Returns a list of the calendars
	ret = iphone_msync_recv(msync, &array);
	debug_response(array);

	// Acknowledge the response - Reminders
	array = plist_new_array();
	plist_add_sub_string_el(array, "SDMessageAcknowledgeChangesFromDevice");
	plist_add_sub_string_el(array, "com.apple.Calendars");
	
	// Send acknowledgement
	ret = iphone_msync_send(msync, array);
	plist_free(array);
	array = NULL;

	// Get Response - Returns a list of the calendars
	ret = iphone_msync_recv(msync, &array);
	debug_response(array);

	// Acknowledge the response - Recurrence
	array = plist_new_array();
	plist_add_sub_string_el(array, "SDMessageAcknowledgeChangesFromDevice");
	plist_add_sub_string_el(array, "com.apple.Calendars");
	
	// Send acknowledgement
	ret = iphone_msync_send(msync, array);
	plist_free(array);
	array = NULL;

	// Get Response - Returns a list of the calendars
	ret = iphone_msync_recv(msync, &array);
	debug_response(array);
error:
	if (msync) {
		iphone_msync_free_client(msync);
		msync = NULL;
	}
	if (lckd) {
		iphone_lckd_free_client(lckd);
		lckd = NULL;
	}
	if (device) {
		iphone_free_device(device);
		device = NULL;
	}
	return 0;
}

