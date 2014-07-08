import json
from collections import defaultdict
from switchyard.lib.address import EthAddr,IPAddr
from switchyard.lib.topo.util import *
import networkx as nx
from networkx.readwrite import json_graph
import ipaddress
import copy

nompl = False
try:
    import matplotlib.pyplot as pyp
except ImportError:
    nompl = True

class Interface(object):
    '''
    Class that models a single logical interface on a network
    device.  An interface has a name, 48-bit Ethernet MAC address,
    and (optionally) a 32-bit IPv4 address and mask.
    '''
    def __init__(self, name, ethaddr, ipaddr, netmask):
        self.__name = name
        self.ethaddr = ethaddr
        self.ipaddr = ipaddr
        self.netmask = netmask

    @property
    def name(self):
        return self.__name

    @property
    def ethaddr(self):
        return self.__ethaddr

    @ethaddr.setter
    def ethaddr(self, value):
        if isinstance(value, EthAddr):
            self.__ethaddr = value
        elif isinstance(value, str):
            self.__ethaddr = EthAddr(value)
        elif value is None:
            self.__ethaddr = '00:00:00:00:00:00'
        else:
            self.__ethaddr = value

    @property 
    def ipaddr(self):
        return self.__ipaddr

    @ipaddr.setter
    def ipaddr(self, value):
        if isinstance(value, IPAddr):
            self.__ipaddr = value
        elif isinstance(value, str):
            self.__ipaddr = IPAddr(value)
        elif value is None:
            self.__ipaddr = '0.0.0.0'
        else:
            self.__ipaddr = value

    @property 
    def netmask(self):
        return self.__netmask

    @netmask.setter
    def netmask(self, value):
        if isinstance(value, IPAddr):
            self.__netmask = value
        elif isinstance(value, str):
            self.__netmask = IPAddr(value)
        elif value is None:
            self.__netmask = '255.255.255.255'
        else:
            self.__netmask = value

    def __str__(self):
        s =  "{} mac:{}".format(str(self.name), str(self.ethaddr))
        if str(self.ipaddr) != '0.0.0.0':
            s += " ip:{}/{}".format(str(self.ipaddr), str(self.netmask))
        return s            

class Node(object):
    __slots__ = ['ifnum','__interfaces']
    def __init__(self, *args, **kwargs):
        self.ifnum = 0
        self.__interfaces = {}
        if 'interfaces' in kwargs:
            for ifname,ifstr in kwargs['interfaces'].items():
                ifcomponents = ifstr.split()
                mac = ifcomponents[1][4:]
                ipmask = (None,None)
                if len(ifcomponents) > 2:
                    ipmask = ifcomponents[2].split(':')[1].split('/')
                self.__interfaces[ifname] = Interface(ifname, mac, ipmask[0], ipmask[1])

    @property
    def nodetype(self):
        return self.__class__.__name__

    @property
    def interfaces(self):
        return self.__interfaces

    def getInterface(self, devname):
        return self.__interfaces[devname]

    def addInterface(self, ethaddr=None, ipaddr=None, netmask=None):
        ifname = 'eth{}'.format(self.ifnum)
        self.ifnum += 1
        intf = Interface(ifname, ethaddr, ipaddr, netmask)
        self.__interfaces[ifname] = intf
        return ifname

    def __str__(self):
        s = '{} '.format(self.nodetype)
        s += ' '.join(sorted([str(intf) for intf in self.interfaces.values()]))
        return s 

    def asDict(self):
        ifdict = dict([(ifname,str(ifobj)) for ifname,ifobj in self.__interfaces.items()])
        return {'nodetype':self.__class__.__name__, 'interfaces':ifdict}

class Host(Node):
    def __init__(self, *args, **kwargs):
        Node.__init__(self, *args, **kwargs)

class Switch(Node):
    def __init__(self, *args, **kwargs):
        Node.__init__(self, *args, **kwargs)

class Router(Node):
    def __init__(self, *args, **kwargs):
        Node.__init__(self, *args, **kwargs)

class Encoder(json.JSONEncoder):
    def __init__(self, *args, **kwargs):
        json.JSONEncoder.__init__(self, *args, **kwargs)

    def default(self, o):
        return o.asDict()

class Topology(object):
    __slots__ = ['__nxgraph','__hnum','__snum','__rnum','__auto_macs','__ifnum']
    def __init__(self, name="No name topology", nxgraph=None, auto_macs=True):
        if nxgraph:
            self.__nxgraph = nxgraph
        else:
            self.__nxgraph = nx.Graph(name=name)
        self.__hnum = 0
        self.__snum = 0
        self.__rnum = 0
        self.__auto_macs = auto_macs
        self.__ifnum = 1

    @property
    def name(self):
        return self.__nxgraph.graph['name']

    @name.setter
    def name(self, value):
        self.__nxgraph.graph['name'] = value

    @property
    def auto_macs(self):
        return self.__auto_macs

    @property
    def nxgraph(self):
        return self.__nxgraph

    @nxgraph.setter
    def nxgraph(self, value):
        assert(isinstance(value, nx.Graph))
        self.__nxgraph = value

    def __addNode(self, name, cls):
        '''
        Add a node to the topology
        '''
        if name in self.nodes:
            raise Exception("A node by the name {} already exists.  Can't add a duplicate.".format(name))
        self.__nxgraph.add_node(name)
        self.__nxgraph.node[name]['label'] = name
        self.__nxgraph.node[name]['nodeobj'] = cls()
        self.__nxgraph.node[name]['type'] = cls.__name__

    def getNode(self, name):
        return self.__nxgraph.node[name]

    def getEdge(self, node1, node2):
        return self.__nxgraph[node1][node2]

    def getLink(self, node1, node2):
        return self.getEdge(node1, node2)

    @property
    def links(self):
        return self.__nxgraph.edges(data=False)

    def __getnodes(self, typefilter=None):
        if typefilter:
            return [ n for n,ndict in self.__nxgraph.nodes(data=True) if ndict['type'] == typefilter]
        return self.__nxgraph.nodes()

    @property
    def nodes(self):
        return self.__getnodes()

    @property
    def hosts(self):
        return self.__getnodes('Host')

    @property
    def switches(self):
        return self.__getnodes('Switch')

    @property
    def routers(self):
        return self.__getnodes('Router')

    def addHost(self, name=None):
        '''
        Add a new host node to the topology.
        '''
        if name is None:
            while True:
                name = 'h' + str(self.__hnum)
                self.__hnum += 1
                if name not in self.__nxgraph:
                    break
        self.__addNode(name, Host)
        return name

    def neighbors(self, node):
        return nx.all_neighbors(self.__nxgraph, node)

    def edges_from(self, node):
        return nx.edges(self.__nxgraph, [node])

    def addSwitch(self, name=None):
        '''
        Add a new switch to the topology.
        '''
        if name is None:
            while True:
                name = 's' + str(self.__snum)
                self.__snum += 1
                if name not in self.__nxgraph:
                    break
        self.__addNode(name, Switch)
        return name

    def addRouter(self, name=None):
        '''
        Add a new switch to the topology.
        '''
        if name is None:
            while True:
                name = 'r' + str(self.__rnum)
                self.__rnum += 1
                if name not in self.__nxgraph:
                    break
        self.__addNode(name, Router)
        return name

    def addLink(self, node1, node2, capacity, delay):
        '''
        Add a bidirectional link between node1 and node2 with the given
        capacity and delay to the topology.
        '''
        for n in (node1, node2):
            if not self.__nxgraph.has_node(n):
                raise Exception("No node {} exists for building a link".format(n))
        macs = [None,None]
        if self.__auto_macs:
            for i in range(len(macs)):
                macstr = '{:012x}'.format(self.__ifnum)
                self.__ifnum += 1
                macaddr = ':'.join([ macstr[j:(j+2)] for j in range(0,len(macstr),2)])
                macs[i] = macaddr
        node1if = self.__nxgraph.node[node1]['nodeobj'].addInterface(ethaddr=macs[0])
        node2if = self.__nxgraph.node[node2]['nodeobj'].addInterface(ethaddr=macs[1])
        self.__nxgraph.add_edge(node1, node2)
        capbits = unhumanize_capacity(capacity)
        delaysec = unhumanize_delay(delay)
        self.__nxgraph[node1][node2]['label'] = "{} {}".format(humanize_capacity(capbits), humanize_delay(delaysec))
        self.__nxgraph[node1][node2]['capacity'] = capbits
        self.__nxgraph[node1][node2]['delay'] = delaysec
        self.__nxgraph[node1][node2][node1] = node1if
        self.__nxgraph[node1][node2][node2] = node2if

    def serialize(self):
        '''
        Return a JSON string of the serialized topology
        '''
        return json.dumps(json_graph.node_link_data(self.__nxgraph), cls=Encoder)

    @staticmethod
    def unserialize(jsonstr):
        '''
        Unserialize a JSON string representation of a topology
        '''
        topod = json.loads(jsonstr)
        G = json_graph.node_link_graph(topod)
        for n,ndict in G.nodes(data=True):
            if 'nodeobj' not in ndict:
                raise Exception("Required nodetype information is not present in serialized node {} :{}".format(n, ndict))
            nobj = ndict['nodeobj']
            cls = eval(nobj['nodetype'])
            ndict['nodeobj'] = cls(**dict(ndict))
        t = Topology(nxgraph=G)
        return t

    def __str__(self):
        return self.serialize()

    def assignIPAddresses(self, prefix=None):
        '''
        Assign IP addresses to all interfaces on hosts and routers in the
        network.  
        
        NB: this method assumes that all interfaces are assigned
        addresses on the same subnet.  If you don't want that behavior,
        the setInterfaceAddresses method must be used.
        '''
        if not prefix:
            subnet = ipaddress.IPv4Network('10.0.0.0/8')
        else:
            subnet = ipaddress.IPv4Network(str(prefix),strict=False)

        ipgenerator = subnet.hosts()

        # collect all links; figure out which ones need to be numbered (i.e., 
        # only interfaces connected to hosts and routers)
        nodes_to_number = self.hosts + self.routers

        for u,v in sorted(self.links):
            linkdata = self.getLink(u,v)
            for node in [u,v]:
                if node in nodes_to_number:
                    ifname = linkdata[node]
                    # print ("Got node {} ifname {}".format(node, ifname))
                    intf = self.getNode(node)['nodeobj'].getInterface(ifname)
                    intf.ipaddr = next(ipgenerator)
                    intf.netmask = subnet.netmask

    def getLinkInterfaces(self, node1, node2):
        '''
        Given two node names that identify a link, return the pair of
        interface names assigned at each endpoint (as a tuple in the 
        same order as the nodes given).
        '''
        linkdata = self.getLink(node1,node2)
        return linkdata[node1],linkdata[node1]

    def setInterfaceAddresses(self, node, interface, mac=None, ip=None, netmask=None):
        '''
        Set any one of Ethernet (MAC) address, IP address or IP netmask for
        a given interface on a node.
        '''
        intf = self.getNode(node)['nodeobj'].getInterface(interface)
        if mac:
            intf.ethaddr = mac
        if ip:
            intf.ipaddr = ip
        if netmask:
            intf.netmask = netmask

    def getInterfaceAddresses(self, node, interface):
        '''
        Return the Ethernet and IP+mask addresses assigned to a
        given interface on a node.
        '''
        intf = self.getNode(node)['nodeobj'].getInterface(interface)
        return intf.ethaddr,intf.ipaddr,intf.netmask

    @staticmethod
    def __relabel_graph(nxgraph, prefix=None):
        def renamer(name):
            return '{}_{}'.format(prefix, name)

        # relabel node id's
        nxgraph = nx.relabel_nodes(nxgraph, renamer, copy=True)

        # relabel 'label' in node attributes
        for n,ndict in nxgraph.nodes_iter(data=True):
            nxgraph.node[n]['label'] = n

        # relabel nodename->interfacename attributes in edges
        for u,v,edict in nxgraph.edges_iter(data=True):
            nxgraph[u][v][u] = nxgraph[u][v][u[len(prefix)+1:]] 
            del nxgraph[u][v][u[len(prefix)+1:]] 
            nxgraph[u][v][v] = nxgraph[u][v][v[len(prefix)+1:]] 
            del nxgraph[u][v][v[len(prefix)+1:]] 
        return nxgraph

    def addNodeLabelPrefix(self, prefix=None, copy=False):
        '''
        Rename all nodes in the network from x to prefix_x.  If no prefix
        is given, use the name of the graph as the prefix.
        
        The purpose of this method is to make node names unique so that
        composing two graphs is well-defined.
        '''
        nxgraph = Topology.__relabel_graph(self.__nxgraph, prefix)
        if copy:
            newtopo = copy.deepcopy(self)
            newtopo.nxgraph = nxgraph
            return newtopo
        else:
            # looks like it was done in place
            self.__nxgraph = nxgraph

    def union(self, other, rename=False):
        '''
        Union/add two topologies together to form a larger topology.

        If rename is False, the method assumes that node names 
        don't clash (i.e., you've called addNodeLabelPrefix or 
        you've explicitly chosen names to avoid clashes).  
        If rename is True, nodes/links are relabeled such that the
        new "prefix" for each node is the graph name (i.e., for graph
        name A, node h1 is renamed A_h1).
        
        This method returns a new Topology object and does not modify
        either topology used for unioning.
        '''
        if rename:
            self.nxgraph = Topology.__relabel_graph(self.__nxgraph, self.name)
            other.nxgraph = Topology.__relabel_graph(other.__nxgraph, other.name)
        nxgraph = nx.union(self.nxgraph, other.nxgraph, name="{}_{}".format(self.name, other.name))
        newtopo = Topology(nxgraph=nxgraph, name="{}_{}".format(self.name, other.name))
        return newtopo

def __do_draw(cn_topo):
    if nompl:
        raise Exception("Couldn't import matplotlib: can't show or save a topology plot")

    G = cn_topo.nxgraph
    pos=nx.spring_layout(G)
    nx.draw_networkx(G, pos=pos, with_labels=True) #label=cn_topo.name
    elabels = labels = dict(((u, v), d['label']) for u, v, d in G.edges(data=True))
    nx.draw_networkx_edge_labels(G, pos=pos, edge_labels=elabels, font_size=8)

def show_graph(cn_topo):
    '''
    Display the toolbelt topology (after a conversion to a networkx graph)
    '''
    __do_draw(cn_topo)
    pyp.show()

def save_graph(cn_topo, filename):
    '''
    Save the topology to an image file (after conversion to networkx graph)
    '''
    __do_draw(cn_topo)
    pyp.savefig(filename)

def load_from_file(filename):
    '''
    Load a toolbelt topology from filename and return it.
    '''
    t = None
    with open(filename, 'rU') as infile:
        tdata = infile.read()
        t = Topology.unserialize(tdata)
    return t

def save_to_file(cn_topo, filename):
    '''
    Save a toolbelt topology to a file.
    '''
    jstr = cn_topo.serialize()
    with open(filename, 'w') as outfile:
        outfile.write(jstr)
