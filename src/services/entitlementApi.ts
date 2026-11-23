import { apiRequest } from '../lib/api';
import { parseTrial } from '../lib/entitlement';
export async function getEntitlement() { return parseTrial(await apiRequest('/api/v1/entitlements/me')); }
