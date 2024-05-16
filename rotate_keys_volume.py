import oci
import time
import json
import csv
import sys
config = oci.config.from_file()
key_ocid=''


kms_vault_client=oci.key_management.KmsVaultClient(config)
blockstorage_client = oci.core.BlockstorageClient(config)
resource_search_client = oci.resource_search.ResourceSearchClient(config)
identity_client = oci.identity.IdentityClient(config)


# Create a structured search query
structured_search = oci.resource_search.models.StructuredSearchDetails(
    query="query bootvolume, resources",
    type="Structured",
    matching_context_type=oci.resource_search.models.SearchDetails.MATCHING_CONTEXT_TYPE_NONE
) #, resources
search_response = resource_search_client.search_resources(structured_search)

for resource_summary in search_response.data.items:
    
    boot_volume = blockstorage_client.get_boot_volume(resource_summary.identifier).data
    
    if boot_volume.kms_key_id == None:
        print(f"{boot_volume.display_name} is using Oracle Managed Key")
    else:
        kms_key_id = boot_volume.kms_key_id
        boot_volume_id=boot_volume.id
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
        
        #new_key_version = kms_management_client.create_key_version(kms_key_id).data
        print(f"New key is created")
        response = blockstorage_client.delete_boot_volume_kms_key(boot_volume_id)
        while True:
            get_volume_response = blockstorage_client.get_boot_volume(boot_volume_id).data
            if get_volume_response.lifecycle_state == oci.core.models.Volume.LIFECYCLE_STATE_AVAILABLE:
                print(f"Volume {get_volume_response.display_name} (ID: {get_volume_response.id}) is available.")
                break
                
        print(f"Deleting existing key and default to Oracle Managed Key")
        response = blockstorage_client.update_boot_volume_kms_key(boot_volume_id,update_boot_volume_kms_key_details=oci.core.models.UpdateBootVolumeKmsKeyDetails(
        kms_key_id=kms_key_id))
        print(f"Adding back the key ")
        while True:
            get_volume_response = blockstorage_client.get_boot_volume(boot_volume_id).data
            if get_volume_response.lifecycle_state == oci.core.models.Volume.LIFECYCLE_STATE_AVAILABLE:
                print(f"Volume {get_volume_response.display_name} (ID: {get_volume_response.id}) is available.")
                break
 

        #
        time.sleep(50)



'''

#delete_boot_volume_kms_key_response = blockstorage_client.delete_boot_volume_kms_key(boot_volume_id=volume_id)
print(boot_volume.id)
update_boot_volume_kms_key_response = blockstorage_client.update_boot_volume_kms_key(
    boot_volume_id=volume_id,
    update_boot_volume_kms_key_details=oci.core.models.UpdateBootVolumeKmsKeyDetails(
        kms_key_id='ocid1.key.oc1.iad.bbpi6tfhaaeuk.abuwcljrhqh4t4yaqqnuxysclbbfsjs2iir57puq65bhspylkfuarxvoipca'))
# Get the data from response
'''
