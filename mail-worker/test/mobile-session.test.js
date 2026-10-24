import { beforeEach, describe, expect, it, vi } from 'vitest';
import service from '../src/service/login-service';
import context from '../src/security/user-context';
import constant from '../src/const/constant';
vi.mock('../src/security/user-context', () => ({ default: { getToken: vi.fn() } }));
vi.mock('../src/service/user-service', () => ({ default: {} }));
vi.mock('../src/service/account-service', () => ({ default: {} }));
vi.mock('../src/service/setting-service', () => ({ default: {} }));
vi.mock('../src/service/role-service', () => ({ default: {} }));
vi.mock('../src/service/reg-key-service', () => ({ default: {} }));
vi.mock('../src/service/verify-record-service', () => ({ default: {} }));
describe('mobile session revocation', () => {
  let c;
  beforeEach(() => {
    c = { env: { kv: { get: vi.fn(), put: vi.fn(), delete: vi.fn() } } };
    vi.mocked(context.getToken).mockResolvedValue('first-device');
  });
  it('revokes the current asynchronous token and keeps the other device', async () => {
    c.env.kv.get.mockResolvedValue({ tokens: ['first-device', 'second-device'] });
    await service.logout(c, 3);
    expect(JSON.parse(c.env.kv.put.mock.calls[0][1]).tokens).toEqual(['second-device']);
    expect(c.env.kv.put.mock.calls[0][2]).toEqual({ expirationTtl: constant.TOKEN_EXPIRE });
  });
  it('never removes another session when token is no longer present', async () => {
    c.env.kv.get.mockResolvedValue({ tokens: ['second-device'] });
    await service.logout(c, 3);
    expect(c.env.kv.put).not.toHaveBeenCalled();
    expect(c.env.kv.delete).not.toHaveBeenCalled();
  });
  it('removes an empty session record and handles an already deleted record', async () => {
    c.env.kv.get.mockResolvedValueOnce({ tokens: ['first-device'] }).mockResolvedValueOnce(null);
    await service.logout(c, 3);
    expect(c.env.kv.delete).toHaveBeenCalledTimes(1);
    await service.logout(c, 3);
  });
});
