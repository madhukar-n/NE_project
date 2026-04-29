BGP = {

    'local_as' : 300,
    'router_id' : "3.3.3.3" , 
    'bgp_server_hosts' : ["192.168.0.30"] , 
    'bgp_server_port' : 1026,

    'neighbors': [
        {
            'address': '192.168.0.20',
            'remote_as': 200,
            'remote_port' : 1025,
            'enable_ipv4': True,
            'enable_ipv6': True,
        
        },
    ]
}