from websocket import create_connection
from collections import Counter
import time, random, string, json, requests, datetime, threading, urllib.parse

        
class Client():
    def __init__(self):
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36'}
        with open("asset.json","r") as f:self.assetList=json.loads(f.read())
        with open("setting.json","r") as f:self.settings=json.loads(f.read())
        self.amount = self.settings["amount"]; self.authToken = self.settings["authToken"]; self.currency = self.settings["currency"]; self.walletType = self.settings["walletType"]; self.deviceId = self.settings["deviceId"]
        for i in self.assetList:
            if i["name"] == self.currency:self.assetId=i["id"]; self.assetRic=i["ric"]
        self.pollHost = "wss://as.binomo.com/"
        self.apiHost = "wss://ws.binomo.com/?authtoken="+self.authToken+"&device=web&device_id="+self.deviceId+"&v=2&vsn=2.0.0"
        self.history=[]; self.lastSend=time.time(); self.ref=1; self.stop=False
        self.wsApi = create_connection(self.apiHost,header=self.headers)
        threading.Thread(target=self.hook,daemon=True).start()
        threading.Thread(target=self.pollingMarket,daemon=True).start()
        self.phxJoin()
        print("[ CALLBACK OPERATION ] BOT STARTED...")
        
    def getCurrentBalance(self):
        headers = {'device-id': self.deviceId, 'device-type': 'web','authorization-token': self.authToken, 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36'}
        res = requests.get("https://api.binomo.com/bank/v1/read?locale=en",headers=headers).json()
        for i in res["data"]:
            if i["account_type"] == self.walletType:
                return i["amount"]/100

    def getHistoryMarket(self):
        now = datetime.datetime.now().strftime("%Y-%m-%d")
        return requests.get("https://api.binomo.com/platform/candles/"+urllib.parse.quote_plus(self.assetRic)+"/"+str(now)+"T00:00:00/60?locale=en",headers=self.headers).json()["data"]

    def parseBidTime(self, m=1):
        now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:00")
        bid = datetime.datetime.strptime(now, "%d/%m/%Y %H:%M:%S")+datetime.timedelta(minutes=m)
        return str(int(time.mktime(bid.timetuple())))

    def getBid(self, status, amount):
        if int(datetime.datetime.now().strftime("%S")) < 30:bidTime=self.parseBidTime()
        else:bidTime=self.parseBidTime(2)
        self.sendWs('{"topic":"base","event":"create_deal","payload":{"amount":'+str(amount*100)+',"asset":"'+self.assetRic+'","asset_id":'+str(self.assetId)+',"asset_name":"'+self.currency+'","created_at":'+str(int(time.time()))+',"currency_iso":"IDR","deal_type":"'+self.walletType+'","expire_at":'+bidTime+',"option_type":"turbo","tournament_id":null,"trend":"'+status+'","is_state":false},"ref":"~~","join_ref":"~~"}')

    def hook(self):
        while True:
            data = json.loads(self.wsApi.recv()) 
            if data["event"] == "deal_created":
                print("[ CALLBACK OPERATION ] CREATED DEAL AMOUNT: "+str(int(data["payload"]["amount"]/100)))
            elif data["event"] == "asset_changed_v1":
                print("[ CALLBACK OPERATION ] ASSET RATE CHANGED: "+str(data["payload"]["trading_tools_settings"]["standard"]["payment_rate_standard"])+"%")
                if data["payload"]["trading_tools_settings"]["standard"]["payment_rate_standard"] < 75:self.stop=True
                else:
                    if self.stop:self.stop=False
            else:print(data)
            if time.time() - self.lastSend > 35:
                print("[ CALLBACK OPERATION ] PHOENIX HEARTBEAT")
                self.sendWs('{"topic":"phoenix","event":"heartbeat","payload":{},"ref":"~~"}')

    def phxJoin(self):
        self.sendWs('{"topic":"account","event":"phx_join","payload":{},"ref":"~~","join_ref":"~~"}')
        self.sendWs('{"topic":"user","event":"phx_join","payload":{},"ref":"~~","join_ref":"~~"}')
        self.sendWs('{"topic":"base","event":"phx_join","payload":{},"ref":"~~","join_ref":"~~"}')
        self.sendWs('{"topic":"cfd_zero_spread","event":"phx_join","payload":{},"ref":"~~","join_ref":"~~"}')
        self.sendWs('{"topic":"marathon","event":"phx_join","payload":{},"ref":"~~","join_ref":"~~"}')
        self.sendWs('{"topic":"asset:'+self.assetRic+'","event":"phx_join","payload":{},"ref":"~~","join_ref":"~~"}')

    def pollingMarket(self):
        ws = create_connection(self.pollHost,header=self.headers)
        ws.send('{"action":"subscribe","rics":["'+self.assetRic+'"]}')
        tempData={}; reset=False
        while True:
            try:
                data = json.loads(ws.recv())
                if "assets" in data["data"][0]:
                    timex = data["data"][0]["assets"][0]["created_at"].split(":")[-1].split(".")[0]
                    rate = data["data"][0]["assets"][0]["rate"]
                    if timex == "01":
                        if self.history == []:self.history = self.getHistoryMarket()
                        if reset:
                            if tempData["open"] > tempData["close"]:tempData["stat"]="put"
                            elif tempData["open"] < tempData["close"]:tempData["stat"]="call"
                            self.history.append(tempData)
                            print("[ CALLBACK OPERATION ] CANDLE: "+tempData["stat"].upper())
                            tempData={}; reset=False
                        if tempData == {}:tempData["low"]=rate;tempData["high"]=rate;tempData["open"]=rate
                        else:tempData["low"]=min(rate,tempData["low"]);tempData["high"]=max(rate,tempData["high"])
                    elif timex == "00" and tempData != {}:
                        if reset == False:reset=True
                        tempData["low"]=min(rate,tempData["low"]);tempData["high"]=max(rate,tempData["high"]);tempData["close"]=rate
                    elif tempData != {}:tempData["low"]=min(rate,tempData["low"]);tempData["high"]=max(rate,tempData["high"])
            except:
                ws = create_connection(self.pollHost,header=self.headers)
                ws.send('{"action":"subscribe","rics":["'+self.assetRic+'"]}')
                
    def sendWs(self,data):
        self.wsApi.send(data.replace("~~",str(self.ref)))
        self.ref+=1;self.lastSend = time.time()

    def run(self):
        while True:
            #do something
            time.sleep(1)

client = Client()
client.run()
