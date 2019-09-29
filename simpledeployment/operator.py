import yaml
import kopf
import kubernetes.client


@kopf.on.create('example.org', 'v1', 'simpledeployments')
def create_function(body, spec, **kwargs):
    # The pod definition launched by our SimpleDeployment
    simple_pod = yaml.safe_load(f"""
        apiVersion: v1
        kind: Pod
        spec:
          containers:
          - name: simple
            image: busybox
            command: ["sh", "-x", "-c"]
            args: 
            - |
              echo "I'm so very useful!"
              sleep {spec.get('sleepytime', 0)}
    """)

    # Make the pod a child of our custom resource object by adding namespace, labels etc to the pod definition
    kopf.adopt(simple_pod, owner=body)

    # Create the pod in kubernetes
    api = kubernetes.client.CoreV1Api()
    pod = api.create_namespaced_pod(namespace=simplepod['metadata']['namespace'], body=simplepod)

    # Now "register" the pod with our SimpleDeployment
    return {'children': [pod.metadata.uid]}
