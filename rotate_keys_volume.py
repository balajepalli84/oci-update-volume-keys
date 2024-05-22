import oci
import time
import json
import csv
import sys
import time

config = oci.config.from_file()
key_ocid='ocid1.key.oc1.iad.bbpi6tfhaaeuk.abuwcljrhqh4t4yaqqnuxysclbbfsjs2iir57puq65bhspylkfuarxvoipca'

def get_volume_info(volume_summary):
    if volume_summary.resource_type == 'BootVolume':
        volume_dtls = blockstorage_client.get_boot_volume(volume_summary.identifier)
    elif volume_summary.resource_type == 'Volume':
        volume_dtls = blockstorage_client.get_volume(volume_summary.identifier)
    return volume_dtls.data

def update_key(kms_key_id):
	structured_search = oci.resource_search.models.StructuredSearchDetails(
		query=f"query key resources return allAdditionalFields where identifier = '{kms_key_id}'",
		type="Structured",
		matching_context_type=oci.resource_search.models.SearchDetails.MATCHING_CONTEXT_TYPE_NONE
		)
	kms_search_response = resource_search_client.search_resources(structured_search).data
	vaultId=kms_search_response.items[0].additional_details['vaultId']
	currentKeyVersion=kms_search_response.items[0].additional_details['currentKeyVersion']
	vault_resp = kms_vault_client.get_vault(vault_id=vaultId).data
	vault_management_endpoint= vault_resp.management_endpoint        
	kms_management_client = oci.key_management.KmsManagementClient(config, service_endpoint=vault_management_endpoint)
	key_info = kms_management_client.get_key(kms_key_id).data    
	new_key_version = kms_management_client.create_key_version(kms_key_id).data
	print(f"New key version is created for key {key_info.display_name} in vault {vault_resp.display_name}")

def delete_volume_key(volume_id,resource_type):
    if resource_type == 'BootVolume':
        response = blockstorage_client.delete_boot_volume_kms_key(volume_id)
        while True:
            get_volume_response = blockstorage_client.get_boot_volume(volume_id).data
            if get_volume_response.lifecycle_state == oci.core.models.Volume.LIFECYCLE_STATE_AVAILABLE:
                print(f"Volume {get_volume_response.display_name} (ID: {get_volume_response.id}) is available.")
                break
    elif resource_type == 'Volume':
        response = blockstorage_client.delete_volume_kms_key(volume_id)
        while True:
            get_volume_response = blockstorage_client.get_volume(volume_id).data
            if get_volume_response.lifecycle_state == oci.core.models.Volume.LIFECYCLE_STATE_AVAILABLE:
                print(f"Volume {get_volume_response.display_name} (ID: {get_volume_response.id}) is available.")
                break        
	
    print(f"Deleting existing key and default to Oracle Managed Key")

def update_volume_key(volume_id,kms_key_id,resource_type):
    if resource_type == 'BootVolume':
        response = blockstorage_client.update_boot_volume_kms_key(volume_id,update_boot_volume_kms_key_details=oci.core.models.UpdateBootVolumeKmsKeyDetails(
        kms_key_id=kms_key_id))
        print(f"Adding back the key ")
        while True:
            get_volume_response = blockstorage_client.get_boot_volume(volume_id).data
            if get_volume_response.lifecycle_state == oci.core.models.Volume.LIFECYCLE_STATE_AVAILABLE:
                print(f"Volume {get_volume_response.display_name} (ID: {get_volume_response.id}) is available.")
                break
    elif resource_type == 'Volume':
        response = blockstorage_client.update_volume_kms_key(volume_id,update_volume_kms_key_details=oci.core.models.UpdateVolumeKmsKeyDetails(
        kms_key_id=kms_key_id))
        print(f"Adding back the key ")
        while True:
            get_volume_response = blockstorage_client.get_volume(volume_id).data
            if get_volume_response.lifecycle_state == oci.core.models.Volume.LIFECYCLE_STATE_AVAILABLE:
                print(f"Volume {get_volume_response.display_name} (ID: {get_volume_response.id}) is available.")
                break    
    
   
kms_vault_client=oci.key_management.KmsVaultClient(config)
blockstorage_client = oci.core.BlockstorageClient(config)
resource_search_client = oci.resource_search.ResourceSearchClient(config)
identity_client = oci.identity.IdentityClient(config)


# Create a structured search query
structured_search = oci.resource_search.models.StructuredSearchDetails(
    query="query bootvolume,volume resources",
    type="Structured",
    matching_context_type=oci.resource_search.models.SearchDetails.MATCHING_CONTEXT_TYPE_NONE
) #, resources
search_response = resource_search_client.search_resources(structured_search)
update_key(key_ocid)
for resource_summary in search_response.data.items:
    volume_info = get_volume_info(resource_summary)
    if volume_info.kms_key_id == key_ocid:
        compartment_name=identity_client.get_compartment(volume_info.compartment_id).data.name
        kms_key_id = volume_info.kms_key_id
        volume_id=volume_info.id
        resource_type=resource_summary.resource_type
        print(f"Updating {resource_type} {resource_summary.display_name} in {compartment_name} compartment")        
        #per priduct team update volume key will work even if its the same key operation
        #delete_volume_key(volume_id,resource_type)
        update_volume_key(volume_id,kms_key_id,resource_type)
        print('-'*30)