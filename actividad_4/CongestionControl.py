class CongestionControl:

    SLOW_START = "slow_start"
    CONGESTION_AVOIDANCE = "congestion_avoidance"
    #1.
    def __init__(self, MSS):
        self.MSS = MSS
        self.cwnd = MSS
        self.ssthresh = None
        self.current_state =self.SLOW_START #siempre empieza en slow_start

    ##getters
    #2.
        #retornar el valor cwnd almacenado en su objeto CongestionControl
    def get_cwnd(self):
        return self.cwnd

    def get_ssthresh(self):
        return self.ssthresh

    def get_state(self):
        return self.current_state
    #3.
    #el tamaño de la ventana expresado como la cantidad de MSSs completos que caben en cwnd.
    def get_MSS_in_cwnd(self):
        return int(self.cwnd // self.MSS)

    #6.
    def is_state_slow_start(self):
        return self.current_state == self.SLOW_START

    def is_state_congestion_avoidance(self):
        return self.current_state == self.CONGESTION_AVOIDANCE

    #4.
    #se encargará de manejar los cambios asociados a la recepción de ACKs
    def event_ack_received(self):
        if self.is_state_slow_start():
            self.cwnd += self.MSS
            #puede ser NOne antes del primer timeout!
            if self.ssthresh is not None and self.cwnd >= self.ssthresh:
                self.current_state = self.CONGESTION_AVOIDANCE

        elif self.is_state_congestion_avoidance():
            self.cwnd += self.MSS  / self.get_MSS_in_cwnd()

    #5.
    #encargará de manejar los cambios asociados a que ocurra timeout.

    def event_timeout(self):
        self.ssthresh = int(self.cwnd / 2)
        self.cwnd = self.MSS
        self.current_state = self.SLOW_START



