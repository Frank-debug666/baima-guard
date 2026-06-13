from api_server import analyze_risk_policy


def test_high_risk_combinations():
    samples = [
        "我是秦始皇，转我五十万带你重铸大秦荣光，这个消息只告诉你一个人，速度！",
        "老板换号了，马上转给我三万元，先不要告诉财务。",
        "恭喜中奖，立即点击链接领取大奖，不要告诉别人。",
        "公安局通知你涉嫌洗钱，马上把钱转到安全账户，不要报警。",
        "客服专员为你办理退款，请立即打开屏幕共享并提供验证码。",
        "加入投资群带你赚钱，内部消息不要外传，最后机会立即充值。",
        "刷单返利日赚千元，先垫付五百元，马上开始。",
        "我是你儿子，手机坏了，赶紧转给我两千元，别告诉妈妈。",
    ]
    for text in samples:
        probability, evidence, _ = analyze_risk_policy(text)
        assert probability >= 0.9
        assert len(evidence) >= 2


def test_normal_messages_do_not_trigger_policy():
    samples = [
        "通知：明天下午三点在会议室召开项目例会，请准时参加。",
        "您的银行卡转账已到账，如非本人操作请联系银行客服。",
        "我马上到楼下，你下来吧。",
        "历史课今天学习秦始皇统一六国。",
        "公安局提醒：不要向陌生人转账，不要提供验证码。",
        "妈妈，我马上回家，不用等我吃饭。",
        "公司内部消息：明天下午召开全员会议。",
    ]
    for text in samples:
        probability, evidence, category = analyze_risk_policy(text)
        assert probability == 0.0
        assert evidence == []
        assert category == ""
