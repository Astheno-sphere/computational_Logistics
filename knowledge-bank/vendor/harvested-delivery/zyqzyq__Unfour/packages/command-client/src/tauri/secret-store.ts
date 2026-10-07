import { call } from "./invoke";
import type {
  CredentialCreateInput,
  CredentialDeleteInput,
  CredentialInspectInput,
  CredentialMetadata,
  CredentialRotateInput,
} from "../types";

export function createCredential(input: CredentialCreateInput) {
  return call<CredentialMetadata>("credential_create", { input });
}

export function deleteCredential(input: CredentialDeleteInput) {
  return call<void>("credential_delete", { input });
}

export function inspectCredential(input: CredentialInspectInput) {
  return call<CredentialMetadata>("credential_inspect", { input });
}

export function rotateCredential(input: CredentialRotateInput) {
  return call<CredentialMetadata>("credential_rotate", { input });
}
