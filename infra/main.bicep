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

// Tags that should be applied to all resources.
var tags = {
  'azd-env-name': environmentName
  application: 'python-mcp-bq-server'
}

var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))

// Container Registry
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'mcpbigquerypy${resourceToken}'
  location: location
  tags: tags
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
  tags: tags
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
          value: googleApplicationCredentialsJson
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
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 30
              periodSeconds: 30
              timeoutSeconds: 10
              successThreshold: 1
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 10
              periodSeconds: 10
              timeoutSeconds: 10
              successThreshold: 1
              failureThreshold: 3
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

output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_REGISTRY_NAME string = containerRegistry.name
output SERVICE_API_NAME string = containerApp.name
output SERVICE_API_URI string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output SERVICE_API_IMAGE_NAME string = 'nginx:latest'
