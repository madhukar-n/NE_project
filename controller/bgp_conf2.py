BGP = {

    'local_as' : 200,
    'router_id' : "2.2.2.2" , 
    'bgp_server_hosts' : ["192.168.0.20"] , 
    'bgp_server_port' : 1025,

  'neighbors': [
        {
            'address': '192.168.0.30',
            'remote_as': 300,
            'remote_port' : 1026,
            'enable_ipv4': True,
            'enable_ipv6': True,
        
        },
    ]
}