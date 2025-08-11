targetScope = 'resourceGroup'

@minLength(1)
@maxLength(64)
@description('Name of the environment that can be used as part of naming resource convention')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string = resourceGroup().location

@description('Google Cloud Project ID')
param googleCloudProject string

@secure()
@description('Google Cloud Service Account credentials JSON')
param googleApplicationCredentialsJson string

@description('Id of the user or app to assign application roles')
param principalId string = ''

@description('Enable authentication (true/false)')
param enableAuth string = 'false'

@secure()
@description('API Keys for authentication (comma-separated)')
param apiKeys string = ''

@secure()
@description('JWT Secret for token signing/validation')
param jwtSecret string = ''

var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))

// Tags that should be applied to all resources
var tags = {
  'azd-env-name': environmentName
}

// Key Vault for storing secrets
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-mcp-bq-${resourceToken}'
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: tenant().tenantId
    enabledForTemplateDeployment: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    accessPolicies: principalId != '' ? [
      {
        tenantId: tenant().tenantId
        objectId: principalId
        permissions: {
          secrets: [
            'get'
            'list'
            'set'
            'delete'
          ]
        }
      }
    ] : []
  }
}

// Store Google Cloud credentials in Key Vault
resource googleCredentialsSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'google-application-credentials'
  parent: keyVault
  properties: {
    value: googleApplicationCredentialsJson
  }
}

// Store API keys in Key Vault (if provided)
resource apiKeysSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (apiKeys != '') {
  name: 'api-keys'
  parent: keyVault
  properties: {
    value: apiKeys
  }
}

// Store JWT secret in Key Vault (if provided)
resource jwtSecretSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (jwtSecret != '') {
  name: 'jwt-secret'
  parent: keyVault
  properties: {
    value: jwtSecret
  }
}

// Container Registry
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'mcpbigquerypy${resourceToken}'
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

// Registry Access
resource registryPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (principalId != '') {
  name: guid(subscription().id, resourceGroup().id, principalId, 'acrPullRole')
  scope: containerRegistry
  properties: {
    principalId: principalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d') // AcrPull
  }
}

// Container Apps Environment
resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: 'mcpbigquerypy-env-${resourceToken}'
  location: location
  properties: {
    zoneRedundant: false
  }
}

// Container App
resource containerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: 'mcpbigquerypy-api-${resourceToken}'
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      secrets: [
        {
          name: 'google-credentials'
          keyVaultUrl: googleCredentialsSecret.properties.secretUri
          identity: 'system'
        }
      ]
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: 'system'
        }
      ]
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          name: 'mcp-bigquery-py'
          image: 'nginx:latest' // Placeholder - will be updated by azd deploy
          env: [
            {
              name: 'GOOGLE_CLOUD_PROJECT'
              value: googleCloudProject
            }
            {
              name: 'GOOGLE_APPLICATION_CREDENTIALS_JSON'
              secretRef: 'google-credentials'
            }
            {
              name: 'ENABLE_AUTH'
              value: enableAuth
            }
            {
              name: 'API_KEYS'
              value: apiKeys
            }
            {
              name: 'JWT_SECRET'
              value: jwtSecret
            }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 60
              periodSeconds: 60
              timeoutSeconds: 30
              successThreshold: 1
              failureThreshold: 5
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 30
              periodSeconds: 30
              timeoutSeconds: 30
              successThreshold: 1
              failureThreshold: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
        rules: [
          {
            name: 'http-scale'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
  identity: {
    type: 'SystemAssigned'
  }
}

// Key Vault Access Policy for Container App
resource keyVaultAccessPolicy 'Microsoft.KeyVault/vaults/accessPolicies@2023-07-01' = {
  name: 'add'
  parent: keyVault
  properties: {
    accessPolicies: [
      {
        tenantId: tenant().tenantId
        objectId: containerApp.identity.principalId
        permissions: {
          secrets: [
            'get'
          ]
        }
      }
    ]
  }
}

output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_REGISTRY_NAME string = containerRegistry.name
output AZURE_KEY_VAULT_NAME string = keyVault.name
output SERVICE_API_NAME string = containerApp.name
output SERVICE_API_URI string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output SERVICE_API_IMAGE_NAME string = 'nginx:latest'
