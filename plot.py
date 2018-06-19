import networkx as nx
import matplotlib.pyplot as plt
from graphviz import Digraph


def nodeLabel(node):
    """
    Arguments:
        node {Node} -- Node to generate graphbiz label for.

    Returns:
        str -- Graphviz label for node.
    """

    tx = node.tx
    return '<<B>%d</B><BR/>%s>' % (tx.id, tx.hash()[:4])


visited = set()


def dagToDig(miner, node, digraph=None):
    """
    Arguments:
        miner {Miner} -- Miner object whose blockchain view is the DAG.
        node {Node} -- Current node being examined in the DAG.

    Keyword Arguments:
        digraph {graphviz.Digraph} -- Directed graph being built. (default: {None})

    Returns:
        graphviz.Digraph -- Graph created from miner's DAG.
    """

    global visited
    node_id = node.tx.hash()
    if node in visited:
        return digraph
    if digraph is None:
        digraph = Digraph()
        digraph.graph_attr['rankdir'] = 'RL'
    if node.tx in miner.accepted_tx:
        digraph.node(node_id, label=nodeLabel(node), fillcolor='#ffff66', style='filled')
    else:
        digraph.node(node_id, label=nodeLabel(node))
    visited.add(node)
    for child in node.children:
        child_id = child.tx.hash()
        digraph.edge(child_id, node_id)
        dagToDig(miner, child, digraph)
    return digraph


def plotDag(miner, fname='test.gv'):
    """Plot the DAG of the miner's view of the blockchain.

    Arguments:
        miner {Miner} -- Miner whose DAG we want to plot.

    Keyword Arguments:
        fname {str} -- Filename to output Graphviz Dot File. (default: {'test.gv'})
    """

    global visited
    visited = set()
    digraph = dagToDig(miner, miner.root)
    digraph.render(fname, view=True)


def simplePlot(graph, pos=None):
    """Displays a simple matplotlib plot of a networkx graph
    See https://networkx.github.io/documentation/stable/reference/generated/networkx.drawing.nx_pylab.draw_networkx.html#networkx.drawing.nx_pylab.draw_networkx.

    Arguments:
        graph {networkx.Graph} -- Graph to plot

    Keyword Arguments:
        pos {dict} -- Map of graph node id to tuple of x,y coordinates. (default: {None})
    """

    if pos:
        nx.draw_networkx(graph, with_labels=False, node_size=20, pos=pos)
    else:
        nx.draw_networkx(graph, with_labels=False, node_size=20)
    plt.show()


# Reinstate plotly later if desired.
