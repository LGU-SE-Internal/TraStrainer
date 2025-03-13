class Span():
    def __init__(self, traceID, spanID, parentID, startTime, elapsedTime, serviceName, callType):
        self.traceID = traceID
        self.spanID = spanID
        self.parentID = parentID
        self.startTime = startTime
        self.elapsedTime = elapsedTime
        self.serviceName = serviceName
        self.callType = callType

    def getTraceId(self):
        return self.traceID

    def getSpanId(self):
        return self.spanID

    def getParentId(self):
        return self.parentID

    def getElapsedTime(self):
        return self.elapsedTime

    def getSpanLabel(self):
        return self.serviceName + ":" + self.callType


class Trace():
    def __init__(self, traceID, spans, abnormal=False):
        self.traceID = traceID
        self.spanNum = len(spans)
        self.spans = spans
        self.abnormal = abnormal

    def getTraceId(self):
        return self.traceID

    def getSpanNum(self):
        return self.spanNum

    def getSpans(self):
        return self.spans
