from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel


def topology():

    net = Mininet(link=TCLink, switch=OVSSwitch, build=False , autoSetMacs=True)

    # ---------------- Controllers ----------------
    c1 = net.addController('c1', controller=RemoteController, ip='192.168.0.1', port=6633)
    c2 = net.addController('c2', controller=RemoteController, ip='192.168.0.2', port=6634)
    c3 = net.addController('c3', controller=RemoteController, ip='192.168.0.3', port=6635)

    switches = [net.addSwitch(f's{i}') for i in range(1,16)]

    hosts = []

    # Domain 1 → 10.0.0.0/16
    for i in range(1,6):
        h = net.addHost(f'h{i}', ip=f'10.0.0.{i}/16', defaultRoute=f'dev h{i}-eth0')
        net.addLink(h, switches[i-1])
        hosts.append(h)

    # Domain 2 → 20.0.0.0/16
    for i in range(6,11):
        h = net.addHost(f'h{i}', ip=f'20.0.0.{(i-5)}/16' , defaultRoute=f'dev h{i}-eth0')
        net.addLink(h, switches[i-1])
        hosts.append(h)

    # Domain 3 → 30.0.0.0/16
    for i in range(11,16):
        h = net.addHost(f'h{i}', ip=f'30.0.0.{(i-10)}/16', defaultRoute=f'dev h{i}-eth0')
        net.addLink(h, switches[i-1])
        hosts.append(h)

    #connect the switches
    for i in range(0,4):
        net.addLink(switches[i], switches[i+1])
    for i in range(4,9):
        net.addLink(switches[i], switches[i+1])
    for i in range(9,14):
        net.addLink(switches[i], switches[i+1])
    net.addLink(switches[0],switches[10])

    
    net.build()
    for i in range(0,5):
        switches[i].start([c1])
    for i in range(5,10):
        switches[i].start([c2])
    for i in range(10,15):
        switches[i].start([c3])
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    topology()