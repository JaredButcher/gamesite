import logging
from gameserver.gameclient import GameClient
from gameserver.player import Player
from gameserver.netobj import NetObj
import time
import asyncio
import typing

class GameBase(NetObj):
    def __init__(self, prevGame: typing.Optional['GameBase'] = None):
        self.gameName = prevGame.gameName if prevGame else "None"
        self.maxPlayers = prevGame.maxPlayers if prevGame else 1
        self.owner = None
        self.tickrate = 20
        self.running = False
        self.players: typing.Dict[int, 'Player'] = {}
        if prevGame:
            self.newPlayer(prevGame.owner.client)
            for player in prevGame.players:
                self.newPlayer(player.client)
        super().__init__('game', 0)

    @property
    def playerCount(self):
        return len(self.players)

    @property
    def connectedPlayerCount(self):
        return len(self.connectedPlayers)

    @property
    def connectedPlayers(self):
        return [player for player in self.players.values() if player.client.connected]

    def setOwner(self, newOwner: 'Player'):
        if self.owner:
            self.owner.cmdSetOwner(False)
        newOwner.cmdSetOwner(True)
        self.owner = newOwner

    def rpcStartGame(self):
        self.running = True
        self.rpcAll("rpcStartGame")
        for obj in NetObj.netObjs:
            obj.onStart()
        asyncio.get_event_loop().create_task(self._startGameLoop())

    async def _startGameLoop(self):
        lastTime = time.time()
        while self.running:
            if time.time() - lastTime < 1 / self.tickrate:
                asyncio.sleep(time.time() - lastTime)
            currentTime = time.time()
            self.gameLoop(currentTime - lastTime)
            lastTime = currentTime

    def gameLoop(self, deltatime: float):
        pass

    def close(self):
        self.running = False
        self.rpcAll("__close__", "Game closed")

    def newPlayer(self, client: 'GameClient'):
        if client not in [player.client for player in self.players.values()]:
            if self.maxPlayers > self.connectedPlayerCount:
                logging.log(30, "New Player " + str(self.connectedPlayerCount) + " " + str(client.id) + " " + str(self.maxPlayers) + " " + str(self.connectedPlayerCount))
                self.players[client.id] = Player(client, parent=self)
                client.onDisconnect = self.playerDisconnected
                if self.connectedPlayerCount == 1:
                    self.setOwner(self.players[client.id])
            else:
                client.close({'D': 0, 'P': '__close__', 'A':["Cannot Join, Max Players"]})

    def removePlayer(self, client: 'GameClient'):
        player = self.players.pop(client.id, None)
        if player:
            player.destroy()
        self.rpcTarget(client, "__close__", "Player Removed")

    def playerConnected(self, client: 'GameClient'):
        self.newPlayer(client)

    def playerDisconnected(self, client: 'GameClient'):
        logging.log(30, "Player disconnected " + str(client.id))
        self.removePlayer(client)

    def serialize(self, **kwargs) -> dict:
        return super().serialize(gameName = self.gameName, maxPlayers = self.maxPlayers, running = self.running, **kwargs)

