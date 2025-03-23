class AIManager:
    def __init__(self):
        self.current_npc = None
        self.current_location = None
        
    def set_current_npc(self, npc_id):
        self.current_npc = npc_id
        
    def set_current_location(self, location):
        self.current_location = location 