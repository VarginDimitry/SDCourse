import grpc


channel = grpc.insecure_channel(
    target="dns:///videosvc-headless.media:50051",
    options=[
        ("grpc.service_config", '{"loadBalancingPolicy":"round_robin"}'),
        ("grpc.keepalive_time_ms", 20000),
        ("grpc.keepalive_timeout_ms", 5000),
    ],
)
# stub = VideoStub(channel)
# resp = stub.GetVideo(VideoRequest(id="v_1"))
