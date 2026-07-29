// screenshare.js
const NodeMediaServer = require('node-media-server');

const config = {
  rtmp: {
    port: 1935,
    ip: '0.0.0.0',    // Use 0.0.0.0 to listen on all interfaces (or your local IP)
    chunk_size: 4096,
    gop_cache: true,
    ping: 10,
    ping_timeout: 30
  }
  // No HTTP config block here
};

const nms = new NodeMediaServer(config);
nms.run();

console.log('NodeMediaServer for ScreenShare running on port 1935');
