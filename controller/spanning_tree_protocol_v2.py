from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, lldp
from ryu.lib.packet import ether_types
import heapq


class SpanningTreeSwitch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.datapaths = {}
        self.switch_ports = {}
        self.host_ports = {}
        self.adjacency = {}
        self.spanning_tree = {}

    # ---------------- SWITCH CONNECT ----------------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features(self, ev):
        dp = ev.msg.datapath
        ofp = dp.ofproto
        parser = dp.ofproto_parser

        self.datapaths[dp.id] = dp
        self.switch_ports[dp.id] = {}
        self.host_ports[dp.id] = set()

        # Table-miss → controller
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER)]
        self.add_flow(dp, 0, match, actions)

        # Request ports
        dp.send_msg(parser.OFPPortDescStatsRequest(dp))

    # ---------------- LLDP SEND ----------------
    def send_lldp(self, dp):
        ofp = dp.ofproto
        parser = dp.ofproto_parser

        for port in dp.ports.values():
            if port.port_no == ofp.OFPP_LOCAL:
                continue

            pkt = packet.Packet()
            pkt.add_protocol(
                ethernet.ethernet(
                    dst=lldp.LLDP_MAC_NEAREST_BRIDGE,
                    src=port.hw_addr,
                    ethertype=ether_types.ETH_TYPE_LLDP
                )
            )

            pkt.add_protocol(lldp.lldp([
                lldp.ChassisID(subtype=7, chassis_id=str(dp.id).encode()),
                lldp.PortID(subtype=2, port_id=str(port.port_no).encode()),
                lldp.TTL(ttl=120),
                lldp.End()
            ]))

            pkt.serialize()

            actions = [parser.OFPActionOutput(port.port_no)]
            dp.send_msg(parser.OFPPacketOut(
                datapath=dp,
                buffer_id=ofp.OFP_NO_BUFFER,
                in_port=ofp.OFPP_CONTROLLER,
                actions=actions,
                data=pkt.data
            ))

    # ---------------- PORT INFO ----------------
    @set_ev_cls(ofp_event.EventOFPPortDescStatsReply, MAIN_DISPATCHER)
    def port_desc(self, ev):
        dp = ev.msg.datapath

        for p in ev.msg.body:
            if p.port_no <= 0:
                continue
            self.switch_ports[dp.id][p.port_no] = {
                "neighbour": "host",
                "dpid": None
            }
            self.host_ports[dp.id].add(p.port_no)

        self.send_lldp(dp)

    # ---------------- LLDP HANDLE ----------------
    def handle_lldp(self, dp, pkt, in_port):
        l = pkt.get_protocol(lldp.lldp)

        src = dp.id
        dst = int(l.tlvs[0].chassis_id.decode())
        port = int(l.tlvs[1].port_id.decode())

        self.switch_ports[src][in_port]["neighbour"] = "switch"
        self.switch_ports[src][in_port]["dpid"] = dst

        self.switch_ports[dst][port]["neighbour"] = "switch"
        self.switch_ports[dst][port]["dpid"] = src

        self.host_ports[src].discard(in_port)
        self.host_ports[dst].discard(port)

        self.recompute_tree()

    # ---------------- BUILD GRAPH ----------------
    def build_graph(self):
        graph = {}
        for dpid in self.switch_ports:
            graph.setdefault(dpid, [])
            for port, info in self.switch_ports[dpid].items():
                if info["neighbour"] == "switch":
                    graph[dpid].append((info["dpid"], port))
        return graph

    # ---------------- STP COMPUTE ----------------
    def compute_tree(self, root):
        dist = {n: float("inf") for n in self.adjacency}
        dist[root] = 0
        parent = {}

        pq = [(0, root)]

        while pq:
            d, u = heapq.heappop(pq)
            if d > dist[u]:
                continue

            for v, port in self.adjacency[u]:
                if dist[v] > d + 1:
                    dist[v] = d + 1
                    parent[v] = (u, port)
                    heapq.heappush(pq, (dist[v], v))

        tree = {n: [] for n in self.adjacency}

        for child, (par, port) in parent.items():
            tree[par].append((child, port))
            for nbr, p in self.adjacency[child]:
                if nbr == par:
                    tree[child].append((par, p))

        return tree

    # ---------------- INSTALL FLOWS ----------------
    def install_flows(self):
        for dpid, edges in self.spanning_tree.items():
            dp = self.datapaths[dpid]
            parser = dp.ofproto_parser
            ofp = dp.ofproto

            allowed = {p for _, p in edges} | self.host_ports[dpid]

            for port in self.switch_ports[dpid]:
                match = parser.OFPMatch(in_port=port)

                if port in allowed:
                    actions = [parser.OFPActionOutput(ofp.OFPP_FLOOD)]
                else:
                    actions = []  # DROP

                self.add_flow(dp, 10, match, actions)

    # ---------------- RECOMPUTE ----------------
    def recompute_tree(self):
        self.adjacency = self.build_graph()
        if not self.adjacency:
            return

        root = min(self.adjacency.keys())
        self.spanning_tree = self.compute_tree(root)

        self.logger.info(f"Tree: {self.spanning_tree}")

        self.install_flows()

    # ---------------- PACKET IN ----------------
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in(self, ev):
        msg = ev.msg
        dp = msg.datapath
        parser = dp.ofproto_parser

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            self.handle_lldp(dp, pkt, msg.match["in_port"])
            return

    # ---------------- FLOW ADD ----------------
    def add_flow(self, dp, priority, match, actions):
        parser = dp.ofproto_parser
        ofp = dp.ofproto

        inst = [parser.OFPInstructionActions(
            ofp.OFPIT_APPLY_ACTIONS, actions)]

        dp.send_msg(parser.OFPFlowMod(
            datapath=dp,
            priority=priority,
            match=match,
            instructions=inst
        ))