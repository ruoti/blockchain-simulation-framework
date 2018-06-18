import random
import networkx as nx
import tx
import miner
import plot


class Node:
    """node in the miner's personal view of the blockchain"""

    def __init__(self, t):
        self.tx = t
        self.children = []
        self.depth = 0 #only used by bitcoin
        self.reachable = set()  # set of nodes, populate when attaching a new node to its parent's children. Populate with parent and parent's reachable!


class Iota(miner.Miner):
    name = "Iota"

    def __init__(self, i, gen, g, o):
        miner.Miner.__init__(self, i, gen, g, o)  # calls self.start()
        self.root = Node(gen)
        self.chain = {}  # maps tx hash to nodes whose tx has that hash
        self.chain[gen.hash()] = self.root
        self.front = set([self.root])  # update this as nodes are added instead of recomputing!
        self.accepted = set()  # set of tx I've accepted (only used to avoid spamming tx.history events); don't count on this for reporting, use tx.history instead
        self.root.tx.addEvent(-1, self.id, tx.State.CONSENSUS)
        self.accepted.add(self.root.tx)
        self.sheep = set()  # queue of tx to shepherd
        self.reissue = set()  # temporary set of ids that need to be reissued (populated by checkAll; should be reset every tick)
        self.orphans = []

    def findInChain(self, target):
        """returns the tx from self.chain with the target hash"""
        if target in self.chain:
            return self.chain[target]
        return None

    def addToChain(self, tAdd, sender):
        newn = Node(tAdd)
        temp = [newn] + self.orphans[:]
        self.orphans = []
        first = True
        changed = True
        broadcast = []
        while changed and temp: # keep checking all nodes until nothing changed (or there are no orphans)
            changed = False
            for n in temp:
                t = n.tx
                parents = [(self.findInChain(p), p) for p in t.pointers] # works for both bitcoin and iota
                if None not in [p[0] for p in parents]:
                    assert t.hash() not in self.chain  # make sure I've never seen this tx before
                    t.addEvent(self.over.tick, self.id, tx.State.PRE)
                    self.chain[t.hash()] = n
                    broadcast.append(t)
                    for parent, pointer in parents:
                        assert n not in parent.children
                        parent.children.append(n)
                        newDepth = parent.depth + 1
                        if newDepth > n.depth:
                            n.depth = newDepth
                        n.reachable |= set([parent]) | parent.reachable # only needed in iota
                        if parent in self.front:
                            self.front.remove(parent)
                    self.front.add(n)
                    changed = True
                    temp.remove(n)#remove from temp as we go, copy to self.orphans at the end
                elif first:  # only for new orphan
                    assert sender != self.id  # I'm processing a node I just created but I should never have created an orphan
                    for parent, pointer in parents:
                        if parent is None:
                            self.sendRequest(sender, pointer)
            first = False
        self.orphans = temp
        return broadcast

    def getNewParents(self):
        """returns list of 1 or 2 parent tx for new tx"""
        choices = list(self.front)
        if self.root in choices and len(choices) >= 3:
            choices.remove(self.root)
        choices = [c.tx for c in choices]
        l = len(choices)
        assert l > 0
        if l == 2 or choices == [self.root.tx]:
            return choices
        elif l == 1:
            return [choices[0], random.choice([n.tx for n in self.chain.values() if n.tx not in choices])]  # if there's only one frontier node, we select another node at random
        i = j = 0
        while i == j:
            i = random.randint(0, l-1)
            j = random.randint(0, l-1)
        return [choices[i], choices[j]]

    def reachableByAll(self, node):
        """returns whether node is reachable by all frontier nodes that are keys in reachable
        fronts is set of frontier nodes (with front.reachable)
        """
        for front in list(self.front):
            if node not in front.reachable:
                return False
        return True

    def needsReissue(self, node):
        """returns True if both of node's parents are reachableByAll (means node is too deep to be not accepted/reachableByAll itself and needs reissue)
        fronts is list of frontier nodes (with front.reachable)
        """
        for p in node.tx.pointers:
            if not self.reachableByAll(self.chain[p]):  # don't need to worry about excluding node itself
                return False
        return True

    # ==overwritten methods============

    def makeTx(self):
        """return tx
        make sure to append to self.over.allTx
        """
        newtx = tx.Tx(self.over.tick, self.id, self.over.idBag.getNextId())
        parents = self.getNewParents()
        assert parents  # should always have at least one (genesis tx)
        for parent in parents:
            h = parent.hash()
            assert h in self.chain
            newtx.pointers.append(h)
        self.sheep.add(newtx)
        self.over.allTx.append(newtx)
        return newtx

    def checkReissues(self):
        """a chance for the miner to put its need-to-reissue tx in o.IdBag"""
        for i in self.reissue:
            self.over.idBag.addId(i, self)

    def hasSheep(self):
        """returns whether miner has sheep"""
        if self.sheep:
            return True
        return False

    def process(self, t, sender):
        """update view
        return list of tx to broadcast
        """
        return self.addToChain(t, sender)

    def checkAll(self):
        """check all nodes for consensus (runs an implicit "tau" on each node, but all at once because it's faster)"""
        self.reissue = set()  # only reset when you checkAll so that it stays full!
        for node in self.chain.values():  # go through all nodes
            if self.reachableByAll(node):
                if node.tx not in self.accepted:
                    node.tx.addEvent(self.over.tick, self.id, tx.State.CONSENSUS)
                    self.accepted.add(node.tx)
                if node.tx.id in self.reissue:
                    self.reissue.remove(node.tx.id)
            else:
                if node.tx in self.accepted:
                    node.tx.addEvent(self.over.tick, self.id, tx.State.DISCONSENSED)
                    self.accepted.remove(node.tx)
                if node.tx in self.sheep and self.needsReissue(node):
                    self.reissue.add(node.tx.id)

    def removeSheep(self, i):
        """overseer will call this to tell the miner that it doesn't have to shepherd an id anymore"""
        x = None
        for s in self.sheep:
            if s.id == i:
                x = s
        if x:
            self.sheep.remove(x)
        if i in self.reissue:
            self.reissue.remove(i)
