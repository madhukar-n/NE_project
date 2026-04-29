from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, arp, ipv4

class RoutingController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(RoutingController, self).__init__(*args, **kwargs)

        self.gateway_ips = ["10.1.0.254", "10.2.0.254"]
        self.gateway_mac = "aa:bb:cc:dd:ee:ff"

        self.logger.info("🚀 Routing Controller Started")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        parser = dp.ofproto_parser

        self.logger.info(f"Switch Connected: DPID={dp.id}")

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(
            dp.ofproto.OFPP_CONTROLLER,
            dp.ofproto.OFPCML_NO_BUFFER)]

        inst = [parser.OFPInstructionActions(
            dp.ofproto.OFPIT_APPLY_ACTIONS, actions)]

        dp.send_msg(parser.OFPFlowMod(
            datapath=dp,
            priority=0,
            match=match,
            instructions=inst))

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        parser = dp.ofproto_parser
        ofproto = dp.ofproto
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        self.logger.info(f"📥 Packet In: switch={dp.id}, in_port={in_port}")

        # ---------------- ARP ----------------
        arp_pkt = pkt.get_protocol(arp.arp)
        if arp_pkt:
            self.logger.info(f"🔁 ARP: {arp_pkt.src_ip} → {arp_pkt.dst_ip}")

            # Gateway ARP
            if arp_pkt.dst_ip in self.gateway_ips:
                self.logger.info("✅ Replying as Gateway")
                self.send_arp_reply(dp, in_port,
                                    arp_pkt.src_mac,
                                    arp_pkt.src_ip,
                                    arp_pkt.dst_ip)
                return

            # 🔥 Proxy ARP for hosts
            if arp_pkt.dst_ip in ["10.1.0.1", "10.2.0.1"]:
                self.logger.info(f"📡 Proxy ARP for {arp_pkt.dst_ip}")
                self.send_arp_reply(dp, in_port,
                                    arp_pkt.src_mac,
                                    arp_pkt.src_ip,
                                    arp_pkt.dst_ip)
                return

        # ---------------- IPv4 ----------------
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        if ip_pkt:
            self.logger.info(f"🌐 IPv4: {ip_pkt.src} → {ip_pkt.dst}")

            # 🔥 Routing logic (IMPORTANT FIX)
            if ip_pkt.dst.startswith("10.2."):
                out_port = 2   # towards r2
            elif ip_pkt.dst.startswith("10.1."):
                out_port = 1   # towards r1
            else:
                self.logger.info("❌ Unknown network")
                return

            self.logger.info(f"➡️ Routing to port {out_port}")

            actions = [parser.OFPActionOutput(out_port)]

            out = parser.OFPPacketOut(
                datapath=dp,
                buffer_id=ofproto.OFP_NO_BUFFER,
                in_port=in_port,
                actions=actions,
                data=msg.data)

            dp.send_msg(out)

    def send_arp_reply(self, dp, port, dst_mac, dst_ip, target_ip):
        parser = dp.ofproto_parser

        self.logger.info(f"📤 ARP Reply for {target_ip}")

        pkt = packet.Packet()

        pkt.add_protocol(ethernet.ethernet(
            ethertype=0x0806,
            dst=dst_mac,
            src=self.gateway_mac))

        pkt.add_protocol(arp.arp(
            opcode=arp.ARP_REPLY,
            src_mac=self.gateway_mac,
            src_ip=target_ip,
            dst_mac=dst_mac,
            dst_ip=dst_ip))

        pkt.serialize()

        actions = [parser.OFPActionOutput(port)]

        out = parser.OFPPacketOut(
            datapath=dp,
            buffer_id=dp.ofproto.OFP_NO_BUFFER,
            in_port=dp.ofproto.OFPP_CONTROLLER,
            actions=actions,
            data=pkt.data)

        dp.send_msg(out)