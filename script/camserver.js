const NodeMediaServer = require('node-media-server');

const config = {
  rtmp: {
    port: 1935,
    chunk_size: 4096,
    gop_cache: true,
    ping: 10,
    ping_timeout: 30,
  }
};

const nms = new NodeMediaServer(config);
nms.run();

console.log("NodeMediaServer running on port 1935");
