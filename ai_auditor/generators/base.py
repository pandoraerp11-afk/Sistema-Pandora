from abc import ABC, abstractmethod


class BaseGenerator(ABC):
    def __init__(self, tenant, session):
        self.tenant = tenant
        self.session = session

    @abstractmethod
    def generate(self, *args, **kwargs):
        pass
