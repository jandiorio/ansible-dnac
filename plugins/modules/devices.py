#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2019, Red Hat, inc
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection
from ansible.module_utils.six import iteritems

from ansible_collections.ciscodevnet.ansible_dnac.plugins.module_utils import objects
from ansible_collections.ciscodevnet.ansible_dnac.pluigns.module_utils import devices


def main():
    """Main entry point for Ansible Module"""

    config_spec = {
        'name': dict(),

        'type':  dict(choices=['network', 'compute', 'meraki'], default='network'),

        'address': dict(),

        'username': dict(),
        'password': dict(no_log=True),
        'enable_password': dict(no_log=True),
        'transport': dict(choices=['telnet', 'ssh'], default='ssh'),

        'snmp_ro_community':  dict(),
        'snmp_rw_community': dict(),
        'snmp_retries':  dict(type='int'),
        'snmp_timeout': dict(type='int'),
        'snmp_version':  dict(choices=['v2', 'v3'], default='v2'),
    }

    argument_spec = {
        'config': dict(type='list', elements='dict', options=config_spec),
        'state': dict(choices=['present', 'absent'], default='present')
    }

    module = AnsibleModule(argument_spec=argument_spec,
                           supports_check_mode=True)

    connection = Connection(module._socket_path)

    state = module.params['state']

    result = {'changed': False}

    resp = connection.get('/dna/intent/api/v1/network-device')
    resp = module.from_json(resp)
    resp = resp['response']

    # make sure the api response returned a dict object
    if not isinstance(resp, (dict, list)):
        module.fail_json(
            msg="invalid object type, got {}, expected one of {}".format(type(resp), ','.join((dict, list)))
        )

    # convert each object in the response to a typed object
    api_objects = [objects.ApiObject(o) for o in resp]

    operations = objects.Operations(list(), None, list())

    # If state is set to 'absent' and there is no configuration, just
    # simply remove all of the existing objects from the
    # server
    if not module.params['config']:
        operations.delete.extend(api_objects)

    else:
        for entry in module.params['config']:
            # Create an instance of ConfigObject using the values passed
            # in from the playbook
            config_object = objects.ConfigObject(config_spec, entry)

            # Iterate over all of the `api_objects` and try to find a match
            # to the config_object.  If a match is found it will be set to
            # matched_object otherwise matched_object will be None
            match_rule = objects.matchattr('address', 'managementIpAddress')
            matched_object = objects.match(config_object, api_objects, (match_rule,))

            # If matched_object is None, there was no matching state_object found
            # in the list.  If the state param is set to present, flag the
            # config_object for creation
            if matched_object is None and state == 'present':
                operations.post.append(config_object)

            # If a matched_object is found and state is set to absent, then the
            # matched_object needs to be deleted from the server
            elif matched_object and state == 'absent':
                operations.delete.append(matched_object)

            # Finally if a matched_object is found and the state param is set
            # to "present" (default), check the fields for any changes and
            # add config_object to the edit change set
            elif matched_object:
                module.warn("Unable to detect if any device attributes have changed")
            #    obj = {}
            #    for field in config_object._fields:
            #        value = getattr(config_object, field)
            #        if value is not None and value != getattr(matched_object, field):
            #            obj[key] = value

            #    if obj:
            #        for key, value in iteritems(config_spec):
            #            if value['required'] is True and key not in obj:
            #                obj[key] = value

            #        operations.put.append(objects.ConfigObject(obj, obj))

    url = '/dna/intent/api/v1/network-device'
    result.update({'operation': dict(added=[], removed=[], modified='not supported')})

    for method in ('post', 'put', 'delete'):
        items = getattr(operations, method)
        if items:
            if method == 'post':
                if not module.check_mode:
                    for item in items:
                        connection.post(url, data=objects.serialize(item, mapping=devices.CONFIG_TO_API_MAP))
                result['changed'] = True
                result['operation']['added'].append(item.address)

            #elif method == 'put':
            #    if not module.check_mode:
            #        connection.put(url, data=objects.serialize(item))
            #    result['changed'] = True
            #    result['operation']['modified'].append(item.name)

            elif method == 'delete':
                for item in items:
                    if not module.check_mode:
                        connection.delete('{}/{}'.format(url, item.id))
                    result['changed'] = True
                    result['operation']['removed'].append(item.managementIpAddress)

    module.exit_json(**result)


if __name__ == '__main__':
    main()