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


CONFIG_TO_API_MAP = objects.KeyMap(
    ('port', 'netconfPort', lambda x: str(x)),
    ('description',),
    ('comments',)
)


def main():
    """Main entry point for Ansible Module"""

    config_spec = {
        'port': dict(type='int', required=True),
        'description': dict(),
        'comments': dict()
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

    resp = connection.get('/api/v1/global-credential?credentialSubType=NETCONF')
    resp = module.from_json(resp)

    # make sure the api response returned a dict object
    if not isinstance(resp, (dict, list)):
        module.fail_json(
            msg="invalid object type, got {}, expected one of {}".format(type(resp), ','.join((dict, list)))
        )

    # convert each object in the response to a typed object
    api_objects = [objects.ApiObject(o) for o in resp['response']]

    operations = objects.Operations(list(), list(), list())

    # If state is set to 'absent' and there is no configuration, just
    # simply remove all of the existing objects from the
    # server
    if not module.params['config']:
        operations.delete.extend(api_objects)

    else:
        for entry in module.params['config']:
            # Note: convert the port argument to str because the API expects a
            # string otherwise the match will fail.
            entry['port'] = str(entry['port'])

            config_object = objects.ConfigObject(config_spec, entry)

            # Iterate over all of the `api_objects` and try to find a match
            # to the config_object.  If a match is found it will be set to
            # matched_object otherwise matched_object will be None
            match_rule = objects.matchattr('port', 'netconfPort')
            matched_object = objects.match(config_object, api_objects, (match_rule,))

            # If matched_object is None, there was no matching api_object found
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
                obj = {}
                for field in config_object._fields:
                    value = getattr(config_object, field)

                    api_field = CONFIG_TO_API_MAP.get(field).mapped_key

                    if value is not None and value != getattr(matched_object, api_field):
                        obj[key] = value

                if obj:
                    for key, value in iteritems(config_spec):
                        if value['required'] is True and key not in obj:
                            obj[key] = value

                    operations.put.append(ConfigObject(obj, obj))

    url = '/dna/intent/api/v1/global-credential/netconf'
    result.update({'operation': dict(added=[], removed=[], modified=[])})

    for method in ('post', 'put', 'delete'):
        items = getattr(operations, method)
        if items:
            if method == 'post':
                if not module.check_mode:
                    data = objects.serialize(items, CONFIG_TO_API_MAP)
                    connection.post(url, data=data)
                result['changed'] = True
                result['operation']['added'].extend([int(item.port) for item in items])

            elif method == 'put':
                if not module.check_mode:
                    data = objects.serialize(items, CONFIG_TO_API_MAP)
                    connection.put(url, data=data)
                result['changed'] = True
                result['operation']['added'].extend([int(item.port) for item in items])

            elif method == 'delete':
                for item in items:
                    if not module.check_mode:
                        connection.delete('/dna/intent/api/v1/global-credential/{}'.format(item.id))
                    result['changed'] = True
                    result['operation']['removed'].append(int(item.netconfPort))

    module.exit_json(**result)


if __name__ == '__main__':
    main()
