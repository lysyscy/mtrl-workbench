'use strict';

async function showPermissionRequest() {
  const key = decodeURIComponent(location.hash.slice(1));
  const status = document.querySelector('#status');
  const button = document.querySelector('button');
  if (!key.startsWith('i8RelayPermission:')) return;
  const stored = await chrome.storage.session.get(key);
  const origin = stored[key];
  if (!origin) {
    status.textContent = '授权请求已结束，请回工作台重新发起。';
    return;
  }
  await chrome.storage.session.remove(key);
  document.querySelector('#origin').textContent = origin;
  button.disabled = false;
  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      // Chrome requires an extension-page user gesture for permissions.request().
      if (await chrome.permissions.request({origins: [origin + '/*']})) {
        window.close();
        return;
      }
      status.textContent = '尚未授权。也可以在 i8 标签页点一下扩展图标，临时允许访问。';
    } catch {
      status.textContent = '浏览器未能请求授权。请在 i8 标签页点一下扩展图标。';
    }
    button.disabled = false;
  });
}

void showPermissionRequest();
