from config import db


class JobRun(db.Model):
    """
    Uma linha por execução de rotina automática.

    Existe por dois motivos práticos:

    O primeiro é a tela. Sem registro de execução, a vitrine não consegue
    dizer "atualizado há 2 horas" — e uma lista de oportunidades sem data é
    uma lista em que não dá para confiar, porque ninguém sabe se o preço é de
    hoje ou de três semanas atrás.

    O segundo é o diagnóstico. A atualização roda sozinha e de madrugada;
    quando ela falha, o sintoma que aparece é "os dados pararam", e sem o
    histórico de execução não há onde olhar.
    """

    __tablename__ = "job_runs"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    job_name = db.Column(db.String(50), nullable=False, index=True)
    started_at = db.Column(db.DateTime, nullable=False)
    finished_at = db.Column(db.DateTime)

    # OK | PARCIAL | ERRO. "Parcial" existe porque o ciclo tem várias etapas
    # e a falha de uma não invalida as outras: se o FII falhou e a ação
    # passou, os dados de ação são novos e os de FII são velhos — e a tela
    # precisa poder dizer isso.
    status = db.Column(db.String(10), nullable=False)
    detail = db.Column(db.Text)

    def to_json(self):
        return {
            "job_name": self.job_name,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "status": self.status,
            "detail": self.detail,
        }
