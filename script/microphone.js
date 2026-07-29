const NodeMediaServer = require('node-media-server');
const fs = require('fs');

const config = {
  rtmp: {
    port: 1935,
    chunk_size: 4096,
    gop_cache: true,
    ping: 10,
    ping_timeout: 30
  }
};

const nms = new NodeMediaServer(config);

nms.on('prePublish', (id, StreamPath, args) => {
  console.log(`[NodeEvent on prePublish] id=${id} StreamPath=${StreamPath}`);
  fs.writeFileSync('mic_status.txt', 'connected');
});

nms.on('donePublish', (id, StreamPath, args) => {
  console.log(`[NodeEvent on donePublish] id=${id} StreamPath=${StreamPath}`);
  fs.writeFileSync('mic_status.txt', 'disconnected');
});

nms.run();
