from typing import Dict, Iterable
import sys
from typing import Any
import random
import string

from google.cloud import compute_v1
from google.cloud import storage
from google.api_core.extended_operation import ExtendedOperation

# settings_file = "./settings.conf"

def wait_for_extended_operation(operation: ExtendedOperation, verbose_name: str = "operation", timeout: int = 300) -> Any:
    result = operation.result(timeout=timeout)
    if operation.error_code:
        print(
            f"Error during {verbose_name}: [Code: {operation.error_code}]: {operation.error_message}",
            file=sys.stderr,
            flush=True,
        )
        print(f"Operation ID: {operation.name}", file=sys.stderr, flush=True)
        raise operation.exception() or RuntimeError(operation.error_message)

    if operation.warnings:
        print(f"Warnings during {verbose_name}:\n", file=sys.stderr, flush=True)
        for warning in operation.warnings:
            print(f" - {warning.code}: {warning.message}", file=sys.stderr, flush=True)

    return result

class gcp_integrator:
    def __init__(self, settings_file):
        def get_settings(settings_file):
            with open(settings_file, 'r') as f:
                settings = f.read()
            return dict(x.split("=") for x in settings.split('\n'))
        self.settings = get_settings(settings_file)
        self.get_running_info()
    
       
    def get_running_info(self):
        def list_all_instances(project_id):
            instance_client = compute_v1.InstancesClient()
            request = compute_v1.AggregatedListInstancesRequest()
            request.project = project_id
            request.max_results = 50
            agg_list = instance_client.aggregated_list(request=request)
            all_instances = {}
            for zone, response in agg_list:
                if response.instances:
                    all_instances[zone] = response.instances    
            return all_instances
        
        instances = list_all_instances(self.settings['project_id'])
        up = []
        for zone in list(instances.keys()):
            for j in instances[zone]:
                up.append((j.name, j.network_interfaces[0].access_configs[0].nat_i_p))
        return up

    def create_instance(self):
        def get_instance_template(project_id, template_name):
            template_client = compute_v1.InstanceTemplatesClient()
            return template_client.get(project=project_id, instance_template=template_name)
        def gen_name(project_id):
            letters = string.ascii_lowercase
            name = ''.join(random.choice(letters) for i in range(16))
            names = []
            for x in self.get_running_info():
                names.append(x[0])
            if name in names:
                while name not in names:
                    name = ''.join(random.choice(letters) for i in range(16))
            return name
        
        project_id = self.settings['project_id']
        instance_name = gen_name(project_id)
        zone = self.settings['zone']
        
        config = get_instance_template(project_id, "basic-mk-world")
        instance_client = compute_v1.InstancesClient()

        network_interface = compute_v1.NetworkInterface()
        network_interface.name = config.properties.network_interfaces[0].name
        # hard coded, if types can be known then should be replaced with json vals frm config
        access = compute_v1.AccessConfig()
        access.type_ = compute_v1.AccessConfig.Type.ONE_TO_ONE_NAT.name
        access.name = "External NAT"
        access.network_tier = access.NetworkTier.PREMIUM.name
        network_interface.access_configs = [access]
        
        boot_disk = compute_v1.AttachedDisk()
        initialize_params = compute_v1.AttachedDiskInitializeParams()
        initialize_params.source_image = config.properties.disks[0].initialize_params.source_image
        initialize_params.disk_size_gb = config.properties.disks[0].initialize_params.disk_size_gb
        initialize_params.disk_type =  "zones/"+zone+"/diskTypes/"+config.properties.disks[0].initialize_params.disk_type
        boot_disk.initialize_params = initialize_params
        boot_disk.auto_delete = True
        boot_disk.boot = True

        metadata = compute_v1.Metadata()
        metadata.kind = config.properties.metadata.kind
        metadata.items = config.properties.metadata.items
        metadata.fingerprint = config.properties.metadata.fingerprint

        instance = compute_v1.Instance()
        instance.name = instance_name
        instance.network_interfaces = [network_interface]
        instance.disks = [boot_disk]
        instance.machine_type = "zones/"+zone+"/machineTypes/"+config.properties.machine_type
        instance.metadata = metadata
        
        request = compute_v1.InsertInstanceRequest()
        request.zone = zone
        request.project = project_id
        request.instance_resource = instance

        operation = instance_client.insert(request=request)
        wait_for_extended_operation(operation, "instance creation")
        c = instance_client.get(project=project_id, zone=zone, instance=instance_name)
        return {"name":c.name, "ip":c.network_interfaces[0].access_configs[0].nat_i_p}

    def delete_instance(self, machine_name):
        project_id, zone = self.settings['project_id'], self.settings['zone']
        instance_client = compute_v1.InstancesClient()
        operation = instance_client.delete(project=project_id, zone=zone, instance=machine_name)
        wait_for_extended_operation(operation, "instance deletion")
        return True
    
    def put_file(self, source_file_name, destination_blob_name):
        storage_client = storage.Client()
        bucket = storage_client.bucket(self.settings['bucket_name'])
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(source_file_name)
        return True
    
    def get_file(self, source_blob, dest):
        from google.cloud import storage
        storage_client = storage.Client()
        bucket = storage_client.bucket(self.settings['bucket_name'])
        blob = bucket.blob(source_blob)
        blob.download_to_filename(dest)
        return True
    
    def list_files(self):
        storage_client = storage.Client()
        blobs = storage_client.list_blobs(self.settings['bucket_name'])
        return [blob.name for blob in blobs]

    def list_worlds(self):
        storage_client = storage.Client()
        blobs = storage_client.list_blobs(self.settings['bucket_name'])
        return [ blob.name[7:] for blob in blobs if "worlds" in blob.name and len(blob.name) > 7 ]
    
    def delete_file(self, item):
        storage_client = storage.Client()
        bucket = storage_client.bucket(self.settings['bucket_name'])
        blob = bucket.blob(item)
        blob.delete()
        return True


# print(gcp_integrator(settings_file).list_files())

# print(gcp_integrator(settings_file).create_instance())



