<script>
  import { Hst } from '@histoire/plugin-svelte';
  import TrustBadge from './TrustBadge.svelte';
</script>

<Hst.Story title="components/TrustBadge" group="components">
  <Hst.Variant title="Production (cloud KMS)">
    <TrustBadge result={{
      valid: true,
      signature_provenance: 'cloud_kms',
      signed_by: 'Aurora AI',
      signed_at: '2026-05-09T12:34:00Z',
      key_fingerprint: '0123456789abcdef',
      composite_hash: 'abc123def456...',
      manifest_revision: 7,
      trust_badge: 'production',
      failure_reason: null
    }} />
  </Hst.Variant>

  <Hst.Variant title="Local dev">
    <TrustBadge result={{
      valid: true,
      signature_provenance: 'local_dev',
      signed_by: 'localhost (dev key)',
      signed_at: '2026-05-09T10:00:00Z',
      key_fingerprint: 'deadbeef12345678',
      composite_hash: 'fedcba98765...',
      manifest_revision: 2,
      trust_badge: 'dev',
      failure_reason: null
    }} />
  </Hst.Variant>

  <Hst.Variant title="Sample">
    <TrustBadge result={{
      valid: true,
      signature_provenance: 'sample',
      signed_by: 'Aurora Sample Bundle',
      signed_at: '2026-04-01T00:00:00Z',
      key_fingerprint: '5a7b9e3d4f6c1234',
      composite_hash: 'sample0000...',
      manifest_revision: 0,
      trust_badge: 'sample',
      failure_reason: null
    }} />
  </Hst.Variant>

  <Hst.Variant title="Warning (unsigned)">
    <TrustBadge result={{
      valid: false,
      signature_provenance: 'unsigned',
      signed_by: null,
      signed_at: null,
      key_fingerprint: null,
      composite_hash: null,
      manifest_revision: null,
      trust_badge: 'warning',
      failure_reason: 'Bundle has no methodology certificate'
    }} />
  </Hst.Variant>
</Hst.Story>
