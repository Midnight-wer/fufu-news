import axios from 'axios';

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

// ===== 请求拦截：自动附带 token =====
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('fufu-token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ===== 响应拦截：401 清理 + 自动重试 =====
client.interceptors.response.use(
  (res) => res,
  async (err) => {
    const config = err.config;

    // 401 → 清理 token
    if (err.response?.status === 401) {
      localStorage.removeItem('fufu-token');
      return Promise.reject(err);
    }

    // 自动重试一次（仅网络超时/5xx，不重试 4xx）
    const shouldRetry =
      !config._retried &&
      (err.code === 'ECONNABORTED' || !err.response || err.response.status >= 500);

    if (shouldRetry) {
      config._retried = true;
      // 等待 1s 后重试
      await new Promise((resolve) => setTimeout(resolve, 1000));
      return client(config);
    }

    return Promise.reject(err);
  },
);

export default client;
