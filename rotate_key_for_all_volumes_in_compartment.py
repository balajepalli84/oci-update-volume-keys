import oci
import io
import json
import logging

from fdk import response

Signer = oci.auth.signers.get_resource_principals_signer()
kms_vault_client = oci.key_management.KmsVaultClient(config={}, signer=Signer)#
blockstorage_client = oci.core.BlockstorageClient(config={}, signer=Signer)
resource_search_client = oci.resource_search.ResourceSearchClient(config={}, signer=Signer)
identity_client = oci.identity.IdentityClient(config={}, signer=Signer)
# Keep track of rotated keys
rotated_keys = set()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_volume_info(volume_summary):
    if volume_summary.resource_type == 'BootVolume':
        volume_dtls = blockstorage_client.get_boot_volume(volume_summary.identifier)
    elif volume_summary.resource_type == 'Volume':
        volume_dtls = blockstorage_client.get_volume(volume_summary.identifier)
    else:
        raise ValueError(f"Unknown resource type: {volume_summary.resource_type}")
    return volume_dtls.data

def update_kms_key(kms_key_id):
    if kms_key_id in rotated_keys:
        print(f"Key {kms_key_id} has already been rotated during this execution. Skipping rotation.", flush=True)
        return None
    
    structured_search = oci.resource_search.models.StructuredSearchDetails(
        query=f"query key resources return allAdditionalFields where identifier = '{kms_key_id}'",
        type="Structured",
        matching_context_type=oci.resource_search.models.SearchDetails.MATCHING_CONTEXT_TYPE_NONE
    )
    kms_search_response = resource_search_client.search_resources(structured_search).data
    vault_id = kms_search_response.items[0].additional_details['vaultId']
    current_key_version = kms_search_response.items[0].additional_details['currentKeyVersion']
    vault_resp = kms_vault_client.get_vault(vault_id=vault_id).data
    vault_management_endpoint = vault_resp.management_endpoint
    kms_management_client = oci.key_management.KmsManagementClient(config={}, signer=Signer, service_endpoint=vault_management_endpoint)
    key_info = kms_management_client.get_key(kms_key_id).data
    new_key_version = kms_management_client.create_key_version(kms_key_id).data
    print(f"New key version created for key {key_info.display_name} in vault {vault_resp.display_name}", flush=True)
    
    # Mark key as rotated
    rotated_keys.add(kms_key_id)
    return key_info

def update_volume_key(volume_id, kms_key_id, resource_type):
    if resource_type == 'BootVolume':
        blockstorage_client.update_boot_volume_kms_key(volume_id, 
            update_boot_volume_kms_key_details=oci.core.models.UpdateBootVolumeKmsKeyDetails(kms_key_id=kms_key_id))
    elif resource_type == 'Volume':
        blockstorage_client.update_volume_kms_key(volume_id, 
            update_volume_kms_key_details=oci.core.models.UpdateVolumeKmsKeyDetails(kms_key_id=kms_key_id))
    else:
        raise ValueError(f"Unknown resource type: {resource_type}")
    
    while True:
        if resource_type == 'BootVolume':
            get_volume_response = blockstorage_client.get_boot_volume(volume_id).data
        elif resource_type == 'Volume':
            get_volume_response = blockstorage_client.get_volume(volume_id).data
        
        if get_volume_response.lifecycle_state == oci.core.models.Volume.LIFECYCLE_STATE_AVAILABLE:
            break
    print(f"{volume_id} is updated with the {kms_key_id}", flush=True)

def handler(ctx, data: io.BytesIO = None):    
    try:
        # Create a structured search query and loop over all block volumes
        structured_search = oci.resource_search.models.StructuredSearchDetails(
            query="query bootvolume,volume resources where compartmentId='ocid1.compartment.oc1..aaaaaaaafklcekq7wnwrt4zxeizcrmvhltz6wxaqzwksbhbs73yz6mtpi5za'",
            type="Structured",
            matching_context_type=oci.resource_search.models.SearchDetails.MATCHING_CONTEXT_TYPE_NONE
        )
        search_response = resource_search_client.search_resources(structured_search)

        for resource_summary in search_response.data.items:
            volume_info = get_volume_info(resource_summary)
            if volume_info.kms_key_id is not None:
                # Rotate key only if it hasn't been rotated yet
                if volume_info.kms_key_id not in rotated_keys:
                    key_info = update_kms_key(volume_info.kms_key_id)
                print(f"Updating {resource_summary.resource_type} {resource_summary.display_name} ({volume_info.id}) with Key {volume_info.kms_key_id}", flush=True)
                # Proceed with updating the volume key regardless of rotation
                update_volume_key(volume_info.id, volume_info.kms_key_id, resource_summary.resource_type)
            else:
                print(f"No KMS-CMK on {resource_summary.resource_type} {resource_summary.display_name} ({volume_info.id})", flush=True)
    except (Exception, ValueError) as ex:
        logging.getLogger().info(f'ERROR: {str(ex)} while pricessing -- {resource_summary.resource_type} {resource_summary.display_name} ({volume_info.id}) with Key {volume_info.kms_key_id}')
    return response.Response(
        ctx, response_data=json.dumps(
            {"message": "Invoke Sucessfully"}),
        headers={"Content-Type": "application/json"}
    )
