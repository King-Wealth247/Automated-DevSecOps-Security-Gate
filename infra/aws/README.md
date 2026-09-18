# AWS OIDC provisioning — task 4.3 (FR-26, SEC-03, SEC-04)

One-time setup that lets GitHub Actions reach AWS **without any long-lived
AWS keys in the repository**. A `workflow_dispatch`-only probe workflow then
proves it live.

## What this folder deploys

| Resource | Purpose |
|---|---|
| `GitHubOIDCProvider` (`AWS::IAM::OIDCProvider`) | Trusts GitHub Actions' OIDC tokens (`token.actions.githubusercontent.com`, audience `sts.amazonaws.com`) |
| `GitHubActionsDeployRole` (`AWS::IAM::Role`) | `github-actions-devsecops-deploy` — assumed by Actions on PASS only, trust policy scoped to `repo:King-Wealth247/Automated-DevSecOps-Security-Gate:ref:refs/heads/main` |
| Inline policy `JuiceShopEC2Deploy` | least-privilege: describe-only EC2 (to find the test instance by tag) + `ssm:SendCommand` to **one** instance tagged `DevSecOps=juice-shop` (the task 4.4 instance) + `aws-ssm` document/status passthrough |

Everything is free-tier-eligible (IAM/OIDC incur no cost).

## Prerequisites

- An AWS account and an IAM user/role that can run `cloudformation`,
  `iam`, `sts` (a course account or any admin profile is fine).
- AWS CLI 2.x installed.

## Step 0 — Install the AWS CLI (Windows)

```powershell
choco install awscli -y
# close and reopen the shell, then verify:
aws --version
```

## Step 1 — Configure credentials

Two ways:
- Interactive: `aws configure` (region, e.g. `us-east-1`, access key id/secret).
- Or set env vars `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_DEFAULT_REGION`.

> These local key pair are the ONLY long-lived credential involved, and only
> to provision the stack. The whole point of SEC-03/04 is that they never
> enter the repo — after the probe passes you can delete them. Every
> subsequent AWS call from CI is federated.
>
> Verify your identity targets the account you think it does before
> provisioning: `aws sts get-caller-identity`.

## Step 2 — Create the stack

From the repository root (PowerShell):

```powershell
aws cloudformation deploy `
  --template-file infra/aws/oidc-github-actions.yaml `
  --stack-name devsecops-github-oidc `
  --capabilities CAPABILITY_NAMED_IAM `
  --parameter-overrides `
    GitHubOrg=King-Wealth247 `
    GitHubRepo=Automated-DevSecOps-Security-Gate `
    AllowedRef=refs/heads/main `
    InstanceTagKey=DevSecOps `
    InstanceTagValue=juice-shop
```

> `CAPABILITY_NAMED_IAM` is required because the template creates a named
> IAM role/policy. If that exact provider already exists in your account
> (used by another project), redeploy with `CreateOidcProvider=false` and
> `ExistingOIDCProviderArn=arn:aws:iam::<account>:oidc-provider/token.actions.githubusercontent.com`.
> The OIDC provider certificate thumbprints are included in the template;
> recreate the stack if AWS ever rotates GitHub's certificate and AWS reports
> a thumbprint mismatch.

Then read the role ARN:

```powershell
aws cloudformation describe-stacks --stack-name devsecops-github-oidc `
  --query "Stacks[0].Outputs[?OutputKey=='DeployRoleArn'].OutputValue" --output text
```

## Step 3 — Point GitHub at the role

Repo → **Settings → Secrets and variables → Actions → Variables** → add two
**repository variables** (they are not secrets — they carry no credential):

| Variable | Value |
|---|---|
| `AWS_REGION` | the region you deployed to, e.g. `us-east-1` |
| `AWS_ASSUME_ROLE_ARN` | the `DeployRoleArn` output, e.g. `arn:aws:iam::123456789012:role/github-actions-devsecops-deploy` |

## Step 4 — Prove it (task 4.3 validation)

1. Commit + push these three files (the template, the probe workflow, this README).
2. Actions tab → select **AWS OIDC Federation Test (task 4.3)** → **Run workflow**.
3. Open the run log: the **Print the assumed identity** step must print an ARN ending in
   `role/github-actions-devsecops-deploy`, with no `AccessDenied`.

That output is exactly the task-4.3 acceptance criterion: *`aws sts
assume-role-with-web-identity` succeeds from a test workflow run.*

## Notes for task 4.4 / 4.5

- The EC2 instance you create in task 4.4 MUST carry the tag `DevSecOps=juice-shop`
  (in the deploy region) — the SSM grant is tag-scoped, so an untagged
  instance is unreachable by design (and every other instance is, too).
- The instance also needs its own SSM-managed instance role
  (`AmazonSSMManagedInstanceCore`) for Run Command to reach it from the
  federated role; that is provisioned with the instance in task 4.4.
- Hardening at 4.5: once the real deploy job lands in `ci.yml`, tighten the
  trust policy with `StringEquals "token.actions.githubusercontent.com:workflow": ci.yml`
  (stack update, no recreation) so no *other* workflow in the repo can assume
  the role. The probe kept its own workflow file precisely so this hardening
  is added with the deploy job, not before it.

## Troubleshooting

- `AccessDenied` on `cloudformation:DescribeStacks`/`CreateChangeSet`/etc.
  when running Step 2 → your *local* AWS user (the one running the `aws`
  CLI, not the role being created) lacks CloudFormation/IAM permissions.
  Either attach `AdministratorAccess` temporarily, or attach the scoped
  bootstrap policy in `infra/aws/PROVISIONER_POLICY.md` — either way, remove
  it again once the stack + probe succeed.
- `AccessDenied` on `sts:AssumeRoleWithWebIdentity` → stack params/trust policy
  mismatch: confirm `vars.AWS_ASSUME_ROLE_ARN` is the exact `DeployRoleArn`,
  and that the trigger was on `main`.
- `Token has expired` / audit errors → the probe workflow must run from the
  repo's default branch; `id-token: write` must stay in `permissions`.
- Action error "Unable to locate credentials" → `AWS_REGION` variable is
  empty/unset.
- Stack `CREATE_FAILED` on the OIDC provider → an existing provider with the
  same URL already exists; reuse it with `CreateOidcProvider=false` (see Step 2).
- Wrong account → re-run `aws sts get-caller-identity` before provisioning.