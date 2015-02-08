#!/usr/bin/env python
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


# This example performs several tasks on Google Compute Engine.  It can be run
# directly or can be imported into an interactive python session.  This can
# also serve as an integration test for the GCE Node Driver.
#
# To run interactively:
#    - Make sure you have valid values in secrets.py
#      (For more information about setting up your credentials, see the
#      libcloud/common/google.py docstring)
#    - Run 'python' in this directory, then:
#        import gce_demo
#        gce = gce_demo.get_gce_driver()
#        gce.list_nodes()
#        etc.
#    - Or, to run the full demo from the interactive python shell:
#        import gce_demo
#        gce_demo.CLEANUP = False               # optional
#        gce_demo.MAX_NODES = 4                 # optional
#        gce_demo.DATACENTER = 'us-central1-a'  # optional
#        gce_demo.main_compute()                # 'compute' only demo
#        gce_demo.main_load_balancer()          # 'load_balancer' only demo
#        gce_demo.main_dns()                    # 'dns only demo
#        gce_demo.main()                        # all demos / tests

import os.path
import sys

try:
    import secrets
except ImportError:
    print('"demos/secrets.py" not found.\n\n'
          'Please copy secrets.py-dist to secrets.py and update the GCE* '
          'values with appropriate authentication information.\n'
          'Additional information about setting these values can be found '
          'in the docstring for:\n'
          'libcloud/common/google.py\n')
    sys.exit(1)

# Add parent dir of this file's dir to sys.path (OS-agnostically)
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(__file__),
                                 os.path.pardir)))

from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.common.google import ResourceNotFoundError
from libcloud.loadbalancer.types import Provider as Provider_lb
from libcloud.loadbalancer.providers import get_driver as get_driver_lb
from libcloud.dns.types import Provider as Provider_dns
from libcloud.dns.providers import get_driver as get_driver_dns

# Which tests to run, toogle boolean to enable/disable sections
WHICH_TESTS = {
    'compute': True,
    'load-balancer': True,
    'dns': True,
}

# Maximum number of 1-CPU nodes to allow to run simultaneously
MAX_NODES = 5

# String that all resource names created by the demo will start with
# WARNING: Any resource that has a matching name will be destroyed.
DEMO_BASE_NAME = 'lct'

# Datacenter to create resources in
DATACENTER = 'us-central1-f'

# Clean up resources at the end (can be set to false in order to
# inspect resources at the end of the run). Resources will be cleaned
# at the beginning regardless.
CLEANUP = True

args = getattr(secrets, 'GCE_PARAMS', ())
kwargs = getattr(secrets, 'GCE_KEYWORD_PARAMS', {})

# Add datacenter to kwargs for Python 2.5 compatibility
kwargs = kwargs.copy()
kwargs['datacenter'] = DATACENTER

# ==== HELPER FUNCTIONS ====
def get_gce_driver():
    driver = get_driver(Provider.GCE)(*args, **kwargs)
    return driver

def get_gcelb_driver(gce_driver=None):
    # The GCE Load Balancer driver uses the GCE Compute driver for all of its
    # API calls.  You can either provide the driver directly, or provide the
    # same authentication information so the LB driver can get its own
    # Compute driver.
    if gce_driver:
        driver = get_driver_lb(Provider_lb.GCE)(gce_driver=gce_driver)
    else:
        driver = get_driver_lb(Provider_lb.GCE)(*args, **kwargs)
    return driver

def get_dns_driver(gce_driver=None):
    # The Google DNS driver uses the GCE Compute driver for all of its
    # API calls.  You can either provide the driver directly, or provide the
    # same authentication information so the LB driver can get its own
    # Compute driver.
    if gce_driver:
        driver = get_driver_dns(Provider_dns.GCE)(gce_driver=gce_driver)
    else:
        driver = get_driver_dns(Provider_dns.GCE)(*args, **kwargs)
    return driver

def display(title, resource_list=[], use_prefix=True):
    """
    Display a list of resources.

    :param  title: String to be printed at the heading of the list.
    :type   title: ``str``

    :param  resource_list: List of resources to display
    :type   resource_list: Any ``object`` with a C{name} attribute

    :param  use_prefix: If True, prefix output lines with '=> ', but
                        only if the resource item's name begins
                        with DEMO_BASE_NAME
    :type   use_prefix: ``bool``
    """
    print('%s%s:' % (use_prefix and '=> ' or '', title))
    for item in resource_list[:10]:
        if item.name.startswith(DEMO_BASE_NAME):
            print('%s   %s' % (use_preifx and '=> ' or '  ', item.name))
        else:
            print('        %s' % item.name)


def clean_up(gce, base_name, node_list=None, resource_list=None):
    """
    Destroy all resources that have a name beginning with 'base_name'.

    :param  base_name: String with the first part of the name of resources
                       to destroy
    :type   base_name: ``str``

    :keyword  node_list: List of nodes to consider for deletion
    :type     node_list: ``list`` of :class:`Node`

    :keyword  resource_list: List of resources to consider for deletion
    :type     resource_list: ``list`` of I{Resource Objects}
    """
    if node_list is None:
        node_list = []
    if resource_list is None:
        resource_list = []
    # Use ex_destroy_multiple_nodes to destroy nodes
    del_nodes = []
    for node in node_list:
        if node.name.startswith(base_name):
            del_nodes.append(node)

    result = gce.ex_destroy_multiple_nodes(del_nodes)
    for i, success in enumerate(result):
        if success:
            display('   Deleted %s' % del_nodes[i].name)
        else:
            display('   Failed to delete %s' % del_nodes[i].name)

    # Destroy everything else with just the destroy method
    for resource in resource_list:
        if resource.name.startswith(base_name):
            try:
                resource.destroy()
            except ResourceNotFoundError:
                display('   Not found: %s(%s)' % (resource.name,
                                                  resource.__class__.__name__))
            except:
                class_name = resource.__class__.__name__
                display('   Failed to Delete %s(%s)' % (resource.name,
                                                        class_name))
                raise


# ==== COMPUTE CODE STARTS HERE ====
def main_compute():
    gce = get_gce_driver()
    # Get project info and print name
    project = gce.ex_get_project()
    display('=> Project: %s' % project.name)

    # == Get Lists of Everything and Display the lists (up to 10) ==
    # These can either just return values for the current datacenter (zone)
    # or for everything.
    all_nodes = gce.list_nodes(ex_zone='all')
    display('Nodes', all_nodes, False)

    all_addresses = gce.ex_list_addresses(region='all')
    display('Addresses', all_addresses, False)

    all_volumes = gce.list_volumes(ex_zone='all')
    display('Volumes', all_volumes, False)

    # This can return everything, but there is a large amount of overlap,
    # so we'll just get the sizes from the current zone.
    sizes = gce.list_sizes()
    display('Sizes', sizes, False)

    # These are global
    firewalls = gce.ex_list_firewalls()
    display('Firewalls', firewalls, False)

    networks = gce.ex_list_networks()
    display('Networks', networks, False)

    images = gce.list_images()
    display('Images', images, False)

    locations = gce.list_locations()
    display('Locations', locations, False)

    zones = gce.ex_list_zones()
    display('Zones', zones, False)

    snapshots = gce.ex_list_snapshots()
    display('Snapshots', snapshots, False)

    # == Clean up any old demo resources ==
    display('Cleaning up any "%s" resources:' % DEMO_BASE_NAME)
    clean_up(gce, DEMO_BASE_NAME, all_nodes,
             all_addresses + all_volumes + firewalls + networks + snapshots)

    # == Create Node with disk auto-created ==
    if MAX_NODES > 1:
        display('Creating a node with multiple disks using GCE structure:')
        name = '%s-gstruct' % DEMO_BASE_NAME
        img_url = "projects/debian-cloud/global/images/"
        img_url += "backports-debian-7-wheezy-v20141205"
        disk_type_url = "projects/graphite-demos/zones/us-central1-f/"
        disk_type_url += "diskTypes/local-ssd"
        gce_disk_struct = [
            {
                "type": "PERSISTENT",
                "deviceName": '%s-gstruct' % DEMO_BASE_NAME,
                "initializeParams": {
                    "diskName": '%s-gstruct' % DEMO_BASE_NAME,
                    "sourceImage": img_url
                },
                "boot": True,
                "autoDelete": True
            },
            {
                "type": "SCRATCH",
                "deviceName": '%s-gstruct-lssd' % DEMO_BASE_NAME,
                "initializeParams": {
                    "diskType": disk_type_url
                },
                "autoDelete": True
            }
        ]
        node_gstruct = gce.create_node(name, 'n1-standard-1', None,
                                       'us-central1-f',
                                       ex_disks_gce_struct=gce_disk_struct)
        num_disks = len(node_gstruct.extra['disks'])
        display('       Node %s created with %d disks' % (node_gstruct.name,
                                                          num_disks))

        display('Creating Node with auto-created SSD:')
        name = '%s-np-node' % DEMO_BASE_NAME
        node_1 = gce.create_node(name, 'n1-standard-1', 'debian-7',
                                 ex_tags=['libcloud'], ex_disk_type='pd-ssd',
                                 ex_disk_auto_delete=False)
        display('      Node %s created' % name)

        # == Create, and attach a disk ==
        display('Creating a new disk:')
        disk_name = '%s-attach-disk' % DEMO_BASE_NAME
        volume = gce.create_volume(10, disk_name)
        if volume.attach(node_1):
            display ('     Attached %s to %s' % (volume.name, node_1.name))
        display ('      Disabled auto-delete for %s on %s' % (volume.name,
                                                              node_1.name))
        gce.ex_set_volume_auto_delete(volume, node_1, auto_delete=False)

        if CLEANUP:
            # == Detach the disk ==
            if gce.detach_volume(volume, ex_node=node_1):
                display('      Detached %s from %s' % (volume.name,
                                                       node_1.name))

    # == Create Snapshot ==
    display('Creating a snapshot from existing disk:')
    # Create a disk to snapshot
    vol_name = '%s-snap-template' % DEMO_BASE_NAME
    image = gce.ex_get_image('debian-7')
    vol = gce.create_volume(None, vol_name, image=image)
    display('Created disk %s to shapshot' % DEMO_BASE_NAME)
    # Snapshot volume
    snapshot = vol.snapshot('%s-snapshot' % DEMO_BASE_NAME)
    display('      Snapshot %s created' % snapshot.name)

    # == Create Node with existing disk ==
    display('Creating Node with existing disk:')
    name = '%s-persist-node' % DEMO_BASE_NAME
    # Use objects this time instead of names
    # Get latest Debian 7 image
    image = gce.ex_get_image('debian-7')
    # Get Machine Size
    size = gce.ex_get_size('n1-standard-1')
    # Create Disk from Snapshot created above
    volume_name = '%s-boot-disk' % DEMO_BASE_NAME
    volume = gce.create_volume(None, volume_name, snapshot=snapshot)
    display('      Created %s from snapshot' % volume.name)
    # Create Node with Disk
    node_2 = gce.create_node(name, size, image, ex_tags=['libcloud'],
                             ex_boot_disk=volume,
                             ex_disk_auto_delete=False)
    display('      Node %s created with attached disk %s' % (node_2.name,
                                                             volume.name))

    # == Update Tags for Node ==
    display('Updating Tags for %s' % node_2.name)
    tags = node_2.extra['tags']
    tags.append('newtag')
    if gce.ex_set_node_tags(node_2, tags):
        display('      Tags updated for %s' % node_2.name)
    check_node = gce.ex_get_node(node_2.name)
    display('      New tags: %s' % check_node.extra['tags'])

    # == Setting Metadata for Node ==
    display('Setting Metadata for %s' % node_2.name)
    if gce.ex_set_node_metadata(node_2, {'foo': 'bar', 'baz': 'foobarbaz'}):
        display('      Metadata updated for %s' % node_2.name)
    check_node = gce.ex_get_node(node_2.name)
    display('      New Metadata: %s' % check_node.extra['metadata'])

    # == Create Multiple nodes at once ==
    base_name = '%s-multiple-nodes' % DEMO_BASE_NAME
    number = MAX_NODES - 2
    if number > 0:
        display('Creating Multiple Nodes (%s):' % number)
        multi_nodes = gce.ex_create_multiple_nodes(base_name, size, image,
                                                   number,
                                                   ex_tags=['libcloud'],
                                                   ex_disk_auto_delete=True)
        for node in multi_nodes:
            display('      Node %s created.' % node.name)

    # == Create a Network ==
    display('Creating Network:')
    name = '%s-network' % DEMO_BASE_NAME
    cidr = '10.10.0.0/16'
    network_1 = gce.ex_create_network(name, cidr)
    display('      Network %s created' % network_1.name)

    # == Create a Firewall ==
    display('Creating a Firewall:')
    name = '%s-firewall' % DEMO_BASE_NAME
    allowed = [{'IPProtocol': 'tcp',
                'ports': ['3141']}]
    firewall_1 = gce.ex_create_firewall(name, allowed, network=network_1,
                                        source_tags=['libcloud'])
    display('      Firewall %s created' % firewall_1.name)

    # == Create a Static Address ==
    display('Creating an Address:')
    name = '%s-address' % DEMO_BASE_NAME
    address_1 = gce.ex_create_address(name)
    display('      Address %s created with IP %s' % (address_1.name,
                                                     address_1.address))

    # == List Updated Resources in current zone/region ==
    display('Updated Resources in current zone/region:')
    nodes = gce.list_nodes()
    display('Nodes', nodes)

    addresses = gce.ex_list_addresses()
    display('Addresses', addresses)

    firewalls = gce.ex_list_firewalls()
    display('Firewalls', firewalls)

    networks = gce.ex_list_networks()
    display('Networks', networks)

    snapshots = gce.ex_list_snapshots()
    display('Snapshots', snapshots)

    if CLEANUP:
        display('Cleaning up %s resources created.' % DEMO_BASE_NAME)
        clean_up(gce, DEMO_BASE_NAME, nodes,
                 addresses + firewalls + networks + snapshots)
        volumes = gce.list_volumes()
        clean_up(gce, DEMO_BASE_NAME, None, volumes)


# ==== LOAD BALANCER CODE STARTS HERE ====
def main_load_balancer():
    gce = get_gce_driver()
    gcelb = get_gcelb_driver(gce)

    # Existing Balancers
    balancers = gcelb.list_balancers()
    display('Load Balancers', balancers, False)

    # Protocols
    protocols = gcelb.list_protocols()
    display('Protocols:', protocols, False)

    # Healthchecks
    healthchecks = gcelb.ex_list_healthchecks()
    display('Health Checks', healthchecks, False)

    # This demo is based on the GCE Load Balancing Quickstart described here:
    # https://developers.google.com/compute/docs/load-balancing/lb-quickstart

    # == Clean-up and existing demo resources ==
    all_nodes = gce.list_nodes(ex_zone='all')
    firewalls = gce.ex_list_firewalls()
    print('=> Cleaning up any "%s" resources:' % DEMO_BASE_NAME)
    clean_up(gce, DEMO_BASE_NAME, all_nodes,
             balancers + healthchecks + firewalls)

    # == Create 3 nodes to balance between ==
    startup_script = ('apt-get -y update && '
                      'apt-get -y install apache2 && '
                      'hostname > /var/www/index.html')
    tag = '%s-www' % DEMO_BASE_NAME
    base_name = '%s-www' % DEMO_BASE_NAME
    image = gce.ex_get_image('debian-7')
    size = gce.ex_get_size('n1-standard-1')
    number = 3
    metadata = {'items': [{'key': 'startup-script',
                           'value': startup_script}]}
    lb_nodes = gce.ex_create_multiple_nodes(base_name, size, image,
                                            number, ex_tags=[tag],
                                            ex_metadata=metadata,
                                            ignore_errors=False)
    display('Created Nodes', lb_nodes)

    # == Create a Firewall for instances ==
    print('=> Creating a Firewall:')
    name = '%s-firewall' % DEMO_BASE_NAME
    allowed = [{'IPProtocol': 'tcp',
                'ports': ['80']}]
    firewall = gce.ex_create_firewall(name, allowed, source_tags=[tag])
    print('=>    Firewall %s created' % firewall.name)

    # == Create a Health Check ==
    print('=> Creating a HealthCheck:')
    name = '%s-healthcheck' % DEMO_BASE_NAME

    # These are all the default values, but listed here as an example.  To
    # create a healthcheck with the defaults, only name is required.
    hc = gcelb.ex_create_healthcheck(name, host=None, path='/', port='80',
                                     interval=5, timeout=5,
                                     unhealthy_threshold=2,
                                     healthy_threshold=2)
    print('=>    Healthcheck %s created' % hc.name)

    # == Create Load Balancer ==
    print('=> Creating Load Balancer')
    name = '%s-lb' % DEMO_BASE_NAME
    port = 80
    protocol = 'tcp'
    algorithm = None
    members = lb_nodes[:2]  # Only attach the first two initially
    healthchecks = [hc]
    balancer = gcelb.create_balancer(name, port, protocol, algorithm, members,
                                     ex_healthchecks=healthchecks)
    print('=>    Load Balancer %s created' % balancer.name)

    # == Attach third Node ==
    print('=> Attaching additional node to Load Balancer:')
    member = balancer.attach_compute_node(lb_nodes[2])
    print('=>    Attached %s to %s' % (member.id, balancer.name))

    # == Show Balancer Members ==
    members = balancer.list_members()
    print('=> Load Balancer Members:')
    for member in members:
        print('=>    ID: %s IP: %s' % (member.id, member.ip))

    # == Remove a Member ==
    print('=> Removing a Member:')
    detached = members[0]
    detach = balancer.detach_member(detached)
    if detach:
        print('=>    Member %s detached from %s' % (detached.id, balancer.name))

    # == Show Updated Balancer Members ==
    members = balancer.list_members()
    print('=> Updated Load Balancer Members:')
    for member in members:
        print('=>    ID: %s IP: %s' % (member.id, member.ip))

    # == Reattach Member ==
    print('=> Reattaching Member:')
    member = balancer.attach_member(detached)
    print('=>    Member %s attached to %s' % (member.id, balancer.name))

    # == Test Load Balancer by connecting to it multiple times ==
    print('=> Sleeping for 10 seconds to stabilize the balancer...')
    time.sleep(10)
    rounds = 200
    url = 'http://%s/' % balancer.ip
    line_length = 75
    print('=> Connecting to %s %s times:' % (url, rounds))
    for x in range(rounds):
        response = url_req.urlopen(url)
        if PY3:
            output = str(response.read(), encoding='utf-8').strip()
        else:
            output = response.read().strip()
        if 'www-001' in output:
            padded_output = output.center(line_length)
        elif 'www-002' in output:
            padded_output = output.rjust(line_length)
        else:
            padded_output = output.ljust(line_length)
        sys.stdout.write('\r%s' % padded_output)
        sys.stdout.flush()
    print('')

    if CLEANUP:
        balancers = gcelb.list_balancers()
        healthchecks = gcelb.ex_list_healthchecks()
        nodes = gce.list_nodes(ex_zone='all')
        firewalls = gce.ex_list_firewalls()

        print('=> Cleaning up %s resources created.' % DEMO_BASE_NAME)
        clean_up(gce, DEMO_BASE_NAME, nodes,
                 balancers + healthchecks + firewalls)


# ==== GOOGLE DNS CODE STARTS HERE ====
def main_compute():
    gce = get_dns_driver()
    # Get project info and print name
    project = gce.ex_get_project()
    print('=> Project: %s' % project.name)


if __name__ == '__main__':
    if WHAT_TESTS['compute']:
        main_compute()
#    if WHAT_TESTS['load_balancer']:
#        main_load_balancer()
#    if WHAT_TESTS['dns']:
#        main_dns()
