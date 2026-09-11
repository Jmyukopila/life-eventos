import { test, expect } from '@playwright/test';
import { uniqueSuffix } from './constants.ts';
import { loginAsAdmin } from './fixtures.ts';

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Coincide con el aviso de éxito del panel sin depender de las comillas tipográficas exactas. */
function successMatching(action: string, name: string): RegExp {
  return new RegExp(`${action}.*${escapeRegex(name)}`);
}

test('la pestaña Organización crea, renombra, archiva y borra nodos del árbol', async ({ page }) => {
  const suffix = uniqueSuffix();
  const congregationName = `Congregación E2E ${suffix}`;
  const networkName = `Red E2E ${suffix}`;
  const renamedNetworkName = `Red E2E Renombrada ${suffix}`;
  const subnetworkName = `Subred E2E ${suffix}`;
  const groupName = `Grupo E2E ${suffix}`;

  await loginAsAdmin(page);
  await page.getByRole('button', { name: 'Organización', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Organización', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Añadir congregación' })).toBeVisible();

  // Crear congregación → red → subred → grupo, anidados.
  await page.getByRole('button', { name: 'Añadir congregación' }).click();
  const createCongregationDialog = page.getByRole('dialog', { name: 'Añadir congregación' });
  await expect(createCongregationDialog).toBeVisible();
  await createCongregationDialog.getByLabel('Nombre *').fill(congregationName);
  await createCongregationDialog.getByRole('button', { name: 'Crear' }).click();
  await expect(page.getByText(successMatching('Se creó', congregationName))).toBeVisible();
  await expect(page.getByText(congregationName, { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Añadir red' }).click();
  const createNetworkDialog = page.getByRole('dialog', { name: 'Añadir red' });
  await createNetworkDialog.getByLabel('Nombre *').fill(networkName);
  await createNetworkDialog.getByRole('button', { name: 'Crear' }).click();
  await expect(page.getByText(networkName, { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Añadir subred' }).click();
  const createSubnetworkDialog = page.getByRole('dialog', { name: 'Añadir subred' });
  await createSubnetworkDialog.getByLabel('Nombre *').fill(subnetworkName);
  await createSubnetworkDialog.getByRole('button', { name: 'Crear' }).click();
  await expect(page.getByText(subnetworkName, { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Añadir grupo' }).click();
  const createGroupDialog = page.getByRole('dialog', { name: 'Añadir grupo' });
  await createGroupDialog.getByLabel('Nombre *').fill(groupName);
  await createGroupDialog.getByRole('button', { name: 'Crear' }).click();
  await expect(page.getByText(groupName, { exact: true })).toBeVisible();

  // La red aparece anidada bajo la congregación, y el grupo bajo la subred.
  const congregationItem = page.locator('.admin-org-node').filter({ has: page.getByText(congregationName, { exact: true }) }).last();
  await expect(congregationItem.getByText(networkName, { exact: true })).toBeVisible();
  const subnetworkItem = page.locator('.admin-org-node').filter({ has: page.getByText(subnetworkName, { exact: true }) }).last();
  await expect(subnetworkItem.getByText(groupName, { exact: true })).toBeVisible();

  // Renombrar la red.
  await page.getByRole('button', { name: `Renombrar ${networkName}` }).click();
  const renameDialog = page.getByRole('dialog', { name: `Renombrar ${networkName}` });
  await expect(renameDialog).toBeVisible();
  const renameInput = renameDialog.getByLabel('Nombre *');
  await renameInput.fill('');
  await renameInput.fill(renamedNetworkName);
  await renameDialog.getByRole('button', { name: 'Guardar' }).click();
  await expect(page.getByText(successMatching('Se renombró', renamedNetworkName))).toBeVisible();
  await expect(page.getByText(renamedNetworkName, { exact: true })).toBeVisible();
  await expect(page.getByText(networkName, { exact: true })).not.toBeVisible();

  // Archivar y restaurar el grupo.
  await page.getByRole('button', { name: `Archivar ${groupName}` }).click();
  await expect(page.getByText(successMatching('Se archivó', groupName))).toBeVisible();
  const groupItem = page.locator('.admin-org-node').filter({ has: page.getByText(groupName, { exact: true }) }).last();
  await expect(groupItem.getByText('Archivado')).toBeVisible();
  await page.getByRole('button', { name: `Restaurar ${groupName}` }).click();
  await expect(page.getByText(successMatching('Se restauró', groupName))).toBeVisible();
  await expect(groupItem.getByText('Archivado')).not.toBeVisible();

  // Intentar borrar la subred: tiene el grupo como dependencia.
  await page.getByRole('button', { name: `Eliminar ${subnetworkName}` }).click();
  const deleteSubnetworkDialog = page.getByRole('dialog', { name: `Eliminar ${subnetworkName}` });
  await expect(deleteSubnetworkDialog).toBeVisible();
  await deleteSubnetworkDialog.getByRole('button', { name: 'Eliminar definitivamente' }).click();
  await expect(deleteSubnetworkDialog.getByText(/1 grupo/)).toBeVisible();
  await deleteSubnetworkDialog.getByRole('button', { name: 'Entendido' }).click();
  await expect(deleteSubnetworkDialog).not.toBeVisible();
  await expect(page.getByText(subnetworkName, { exact: true })).toBeVisible();

  // Borrar el grupo, que sí es una hoja.
  await page.getByRole('button', { name: `Eliminar ${groupName}` }).click();
  const deleteGroupDialog = page.getByRole('dialog', { name: `Eliminar ${groupName}` });
  await deleteGroupDialog.getByRole('button', { name: 'Eliminar definitivamente' }).click();
  await expect(page.getByText(successMatching('Se eliminó', groupName))).toBeVisible();
  await expect(page.getByText(groupName, { exact: true })).not.toBeVisible();

  // Crear una segunda red con el mismo nombre que la primera (ya renombrada) bajo la misma congregación.
  await page.getByRole('button', { name: 'Añadir red' }).click();
  const secondNetworkDialog = page.getByRole('dialog', { name: 'Añadir red' });
  await secondNetworkDialog.getByLabel('Nombre *').fill(renamedNetworkName);
  await secondNetworkDialog.getByRole('button', { name: 'Crear' }).click();
  await expect(secondNetworkDialog.getByText('Ese nombre ya está en uso entre los hermanos.')).toBeVisible();
  await expect(secondNetworkDialog).toBeVisible();
});
