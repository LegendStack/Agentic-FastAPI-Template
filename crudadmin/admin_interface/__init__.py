from fastapi import FastAPI

class CRUDAdmin:
    def __init__(self, **kwargs):
        self.app = FastAPI()
    def register_model(self, *args, **kwargs):
        pass
    def add_view(self, *args, **kwargs):
        pass
    async def initialize(self):
        pass
