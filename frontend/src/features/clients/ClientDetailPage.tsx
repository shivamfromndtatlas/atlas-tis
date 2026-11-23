import AddRoundedIcon from '@mui/icons-material/AddRounded';
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import DescriptionRoundedIcon from '@mui/icons-material/DescriptionRounded';
import UploadFileRoundedIcon from '@mui/icons-material/UploadFileRounded';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  LinearProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import { useSnackbar } from 'notistack';
import { useRef, useState } from 'react';
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom';

import { api, ApiError } from '../../api/client';
import { useApiMutation, useClient, useFiles, useMe, type ClientContact } from '../../api/hooks';
import { can } from '../../app/navigation';
import { ConfirmDialog, ErrorAlert, FullPageLoader } from '../../components/common';
import { formatDate } from '../../components/format';
import { ClientDialog } from './ClientsPage';

function Field({ label, value }: { label: string; value?: string | null }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography>{value || '—'}</Typography>
    </Box>
  );
}

function ContactDialog({ clientId, onClose }: { clientId: string; onClose: () => void }) {
  const [draft, setDraft] = useState({ name: '', designation: '', email: '', phone: '', is_primary: false });
  const [error, setError] = useState<string | null>(null);
  const save = useApiMutation(
    (body: typeof draft) => api<ClientContact>(`/clients/${clientId}/contacts/`, { method: 'POST', body }),
    ['client'],
  );
  const submit = async () => {
    try {
      await save.mutateAsync(draft);
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not save');
    }
  };
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Add contact</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField label="Name" autoFocus value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
          <TextField
            label="Designation"
            value={draft.designation}
            onChange={(e) => setDraft({ ...draft, designation: e.target.value })}
          />
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField label="Email" value={draft.email} onChange={(e) => setDraft({ ...draft, email: e.target.value })} />
            <TextField label="Phone" value={draft.phone} onChange={(e) => setDraft({ ...draft, phone: e.target.value })} />
          </Stack>
          <FormControlLabel
            control={
              <Switch checked={draft.is_primary} onChange={(e) => setDraft({ ...draft, is_primary: e.target.checked })} />
            }
            label="Primary point of contact"
          />
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={submit} disabled={!draft.name.trim() || save.isPending}>
          Add
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function Documents({ clientId }: { clientId: string }) {
  const { data: me } = useMe();
  const { enqueueSnackbar } = useSnackbar();
  const input = useRef<HTMLInputElement>(null);
  const files = useFiles({ owner_type: 'client', owner_id: clientId });
  const upload = useApiMutation((form: FormData) => api('/files/', { method: 'POST', body: form }), ['files']);

  const onPick = async (fileList: FileList | null) => {
    if (!fileList?.length) return;
    for (const file of Array.from(fileList)) {
      const form = new FormData();
      form.append('file', file);
      form.append('kind', 'contract');
      form.append('owner_type', 'client');
      form.append('owner_id', clientId);
      try {
        await upload.mutateAsync(form);
        enqueueSnackbar(`Uploaded ${file.name}`, { variant: 'success' });
      } catch (e) {
        enqueueSnackbar(`${file.name}: ${e instanceof ApiError ? e.message : 'upload failed'}`, { variant: 'error' });
      }
    }
    if (input.current) input.current.value = '';
  };

  const download = async (id: string) => {
    try {
      const { url } = await api<{ url: string }>(`/files/${id}/download-link/`, { method: 'POST' });
      window.location.assign(url);
    } catch (e) {
      enqueueSnackbar(e instanceof ApiError ? e.message : 'Download failed', { variant: 'error' });
    }
  };

  return (
    <Card>
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
          <Typography variant="h6">Documents</Typography>
          {can(me, 'files.upload') && (
            <>
              <input
                ref={input}
                type="file"
                hidden
                multiple
                accept=".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg"
                onChange={(e) => onPick(e.target.files)}
              />
              <Button size="small" startIcon={<UploadFileRoundedIcon />} onClick={() => input.current?.click()}>
                Upload
              </Button>
            </>
          )}
        </Stack>
        {upload.isPending && <LinearProgress sx={{ mb: 1 }} />}
        <Typography variant="caption" color="text.secondary">
          PDF, Word, text or images. Max 20 MB. Contracts, rate cards, NDAs.
        </Typography>
        <List dense>
          {(files.data?.results ?? []).map((doc) => {
            const latest = doc.versions[0];
            return (
              <ListItem
                key={doc.id}
                disableGutters
                secondaryAction={
                  <Button size="small" onClick={() => download(doc.id)}>
                    Download
                  </Button>
                }
              >
                <ListItemIcon sx={{ minWidth: 36 }}>
                  <DescriptionRoundedIcon />
                </ListItemIcon>
                <ListItemText
                  primary={doc.title}
                  secondary={`v${doc.current_version} · ${formatDate(latest?.created_at)} · ${latest?.uploaded_by ?? ''}`}
                />
              </ListItem>
            );
          })}
          {files.data && !files.data.results.length && (
            <Typography color="text.secondary" sx={{ py: 2 }}>
              No documents yet.
            </Typography>
          )}
        </List>
      </CardContent>
    </Card>
  );
}

export default function ClientDetailPage() {
  const { id = '' } = useParams();
  const { data: me } = useMe();
  const navigate = useNavigate();
  const { enqueueSnackbar } = useSnackbar();
  const { data: client, isLoading, error } = useClient(id);
  const [editing, setEditing] = useState(false);
  const [addingContact, setAddingContact] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const canManage = can(me, 'clients.manage');
  const archive = useApiMutation(() => api(`/clients/${id}/`, { method: 'DELETE' }), ['clients']);

  if (isLoading) return <FullPageLoader />;
  if (error || !client) return <ErrorAlert error={error ?? new Error('Not found')} />;

  return (
    <>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
        <IconButton component={RouterLink} to="/clients" aria-label="Back to clients">
          <ArrowBackRoundedIcon />
        </IconButton>
        <Box sx={{ flexGrow: 1 }}>
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="h5" component="h1">
              {client.name}
            </Typography>
            <Chip size="small" label={client.code} />
            {client.is_internal && <Chip size="small" color="secondary" variant="outlined" label="Internal" />}
            <Chip size="small" variant="outlined" label={String(client.status)} />
          </Stack>
          <Typography color="text.secondary">{client.legal_name}</Typography>
        </Box>
        {canManage && (
          <Stack direction="row" spacing={1}>
            <Button onClick={() => setEditing(true)}>Edit</Button>
            <Button color="error" onClick={() => setArchiving(true)}>
              Archive
            </Button>
          </Stack>
        )}
      </Stack>

      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', lg: '2fr 1fr' } }}>
        <Stack spacing={2}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Details
              </Typography>
              <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, 1fr)' } }}>
                <Field label="Industry" value={client.industry} />
                <Field label="Website" value={client.website} />
                <Field label="Email" value={client.email} />
                <Field label="Phone" value={client.phone} />
                <Field label="Location" value={[client.city, client.state, client.country].filter(Boolean).join(', ')} />
                <Field label="GSTIN / tax ID" value={client.tax_id} />
                <Field label="Account owner" value={client.account_owner_name} />
                <Field label="Active users" value={String(client.user_count)} />
                <Field label="Created" value={formatDate(client.created_at)} />
              </Box>
              {client.notes && (
                <Box sx={{ mt: 2 }}>
                  <Field label="Notes" value={client.notes} />
                </Box>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                <Typography variant="h6">Contacts</Typography>
                {canManage && (
                  <Button size="small" startIcon={<AddRoundedIcon />} onClick={() => setAddingContact(true)}>
                    Add contact
                  </Button>
                )}
              </Stack>
              <List dense>
                {client.contacts.map((c) => (
                  <ListItem key={c.id} disableGutters>
                    <ListItemText
                      primary={
                        <Stack direction="row" spacing={1} alignItems="center">
                          <span>{c.name}</span>
                          {c.is_primary && <Chip size="small" label="Primary" color="primary" variant="outlined" />}
                        </Stack>
                      }
                      secondary={[c.designation, c.email, c.phone].filter(Boolean).join(' · ')}
                    />
                  </ListItem>
                ))}
                {!client.contacts.length && (
                  <Typography color="text.secondary" sx={{ py: 1 }}>
                    No contacts yet.
                  </Typography>
                )}
              </List>
            </CardContent>
          </Card>
        </Stack>
        <Documents clientId={client.id} />
      </Box>

      {editing && <ClientDialog client={client} onClose={() => setEditing(false)} />}
      {addingContact && <ContactDialog clientId={client.id} onClose={() => setAddingContact(false)} />}
      <ConfirmDialog
        open={archiving}
        title={`Archive ${client.name}?`}
        body="The client is hidden from lists. Its history and audit trail are kept, and an admin can restore it."
        confirmLabel="Archive"
        destructive
        busy={archive.isPending}
        onClose={() => setArchiving(false)}
        onConfirm={async () => {
          await archive.mutateAsync(undefined);
          enqueueSnackbar('Client archived', { variant: 'success' });
          navigate('/clients');
        }}
      />
    </>
  );
}
