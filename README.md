# kopf-introduction
An introduction to kopf - python kubernetes operator framework https://kopf.readthedocs.io/en/latest/, inspired by and totally copied a lot from the awesome examples in https://github.com/zalando-incubator/kopf

## About this introduction

In this short introduction into the kopf framework, we'll be implementing a simple loadtesting tool for applications running inside of Kubernetes. This will give us the possibility to learn what an operator in the context of Kubernetes is and we'll get to know kopf step-by-step along the way.

## What is an operator?

An operator in the context of Kubernetes is an application that implements the controller pattern on a custom resource. So in the end it could be described as an infinit loop watching a custom defined resource in the Kubernetes API and then reconciling, meaning matching the state in the "real world" with the state described in the custom resource.

## Building the simplest operator with kopf

### Installing kopf

```bash
pip install kopf
```

### The SimpleDeployment CRD

A CustomResourceDefinition is a Kubernetes object that defines a custom extension of the Kubernetes API. In addition to the following example a CRD can be defined with an OpenAPIv3 schema which will lead to all resources of that type be validated by Kubernetes automatically (for more info have a look [here](https://kubernetes.io/blog/2019/06/20/crd-structural-schema/)).

```yaml
apiVersion: apiextensions.k8s.io/v1beta1
kind: CustomResourceDefinition
metadata:
  name: simple.example.org
spec:
  scope: Namespaced
  group: example.org
  versions:
    - name: v1
      served: true
      storage: true
  names:
    kind: SimpleDeployment
    plural: simpledeployments
    singular: simpledeployment
    shortNames:
      - simdep
      - sd
  additionalPrinterColumns:
    - name: Children
      type: string
      priority: 0
      JSONPath: .status.child
      description: The child pod created by the operator.
```

```bash
kubectl apply -f simpledeployment-crd.yaml
```

### The SimpleDeployment operator

Now let's implement a very useful operator that will start exactly on pod for every SimpleDeployment.

```python
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
```

Start the operator by executing `kopf run simpledeployment/operator.py --verbose`

Now let's see if it works:

```yaml
apiVersion: example.org/v1
kind: SimpleDeployment
metadata:
  name: example-01
  labels:
    app: simple-app
spec:
  sleepytime: "120"
```

In another shell just execute `kubectl apply -f example-01.yaml`

## Creating our CustomResourceDefinition LoadTest

```yaml
apiVersion: apiextensions.k8s.io/v1beta1
kind: CustomResourceDefinition
metadata:
  name: load.example.org
spec:
  scope: Namespaced
  group: example.org
  versions:
    - name: v1
      served: true
      storage: true
  names:
    kind: LoadTest
    plural: loadtests
    singular: loadtest
    shortNames:
      - ld
  additionalPrinterColumns:
    - name: Children
      type: string
      priority: 0
      JSONPath: .status.children
      description: The children pods created by the operator.
    - name: State
      type: string
      priority: 0
      JSONPath: .status.state
      description: The state of the loadtest can be pending, executing, failed or finished.
```

A sample loadtest object would look like this:
```yaml
apiVersion: example.org/v1
kind: LoadTest
metadata:
  name: example-02
  labels:
    app: loadtest
spec:
  # how many replicas should be spawned
  replicas: 5
  test:
    method: "GET"
    serviceName: "nginx"
    path: "/"
    repeat: 10

```

## Implementing the distributed loadtesting operator - DiLO

So what we'll expect our operator to do:
- when a LoadTest object is created:
  - set `.status.state` to `pending`
  - start `${spec.replicas}` pods
  - set `.status.state` to `executing`
- wait for children pods finishing
  - if there is an error, set `.status.state` to `failed`
  - when pods are finished set `.status.state` to `finished`
- when a LoadTest object is deleted:
  - delete all children pods
- when a LoadTest object is updated:
  - delete all children pods
  - see: when a LoadTest object is created

