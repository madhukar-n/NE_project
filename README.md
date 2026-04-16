## Project Phases & Task List

### Phase 1: Environment & Topology Design
* **Domain Specification**: Define Autonomous System (AS) boundaries and IDs for at least two distinct network domains.
* **Mininet Topology Scripting**: Develop a Python script to instantiate a multi-AS topology. Each domain must contain:
    - A local Open vSwitch (OVS).
    - A dedicated host subnet (e.g., `10.1.0.0/24` for AS1, `10.2.0.0/24` for AS2).
    - A border link connecting the two domain switches.
* **Multi-Controller Configuration**: Configure each domain switch to connect to a unique Ryu controller instance (e.g., `localhost:6633` and `localhost:6653`).

### Phase 2: Controller East-West Interface
* **BGP Speaker Integration**: Utilize `ryu.services.protocols.bgp` to initialize a BGP speaker on each Ryu instance.
* **Neighbor Peering**: Establish BGP peering sessions between controllers using their management IP addresses to facilitate route exchange.
* **Route Advertisement**: Implement logic to advertise local host subnets to the neighboring controller upon network startup.

### Phase 3: Forwarding Logic & Data Plane Management
* **Inter-Domain Flow Rules**: Create a Ryu handler to install flow entries that redirect packets destined for external subnets toward the border gateway link.
* **ARP Proxy Implementation**: Develop a custom ARP handler in Ryu to resolve MAC addresses for cross-domain hosts, preventing broadcast storms across AS boundaries.
* **Packet-In Logic**: Refine `_packet_in_handler` to distinguish between local switching and inter-domain routing based on the BGP RIB (Routing Information Base).

### Phase 4: Integration & Verification
* **Execution Automation**: Create a startup script (`start_lab.sh`) to automate the cleanup of Mininet, launching multiple Ryu controllers, and initializing the topology.
* **Connectivity Testing**: Perform `pingall` and `iperf` tests to verify reachability and throughput across the multi-domain framework.
* **Protocol Analysis**: Use Wireshark/Tshark to capture and analyze BGP `UPDATE` messages and OpenFlow `FLOW_MOD` messages.

### Phase 5: Evaluation
* **Convergence Metrics**: Measure the time required for the framework to establish full reachability after controllers are initialized.
* **Control Plane Overhead**: Quantify the ratio of control traffic (BGP/OpenFlow) to data plane traffic during standard operation.
