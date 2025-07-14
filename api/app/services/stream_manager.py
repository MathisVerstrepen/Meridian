class StreamManager:
    def __init__(self):
        self.active_streams: dict[str, bool] = {}

    def cancel_stream(self, graph_id: str, node_id: str) -> bool:
        key = f"{graph_id}:{node_id}"
        if key in self.active_streams:
            self.active_streams[key] = False
            return True
        return False

    def is_active(self, graph_id: str, node_id: str) -> bool:
        key = f"{graph_id}:{node_id}"
        return self.active_streams.get(key, False)

    def set_active(self, graph_id: str, node_id: str, active: bool):
        key = f"{graph_id}:{node_id}"
        if active:
            self.active_streams[key] = True


class StreamManagerSingleton:
    _instance = None

    @staticmethod
    def get_instance():
        if StreamManagerSingleton._instance is None:
            StreamManagerSingleton._instance = StreamManager()
        return StreamManagerSingleton._instance


stream_manager = StreamManagerSingleton.get_instance()
