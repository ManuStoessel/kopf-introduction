import yaml
import kopf
import kubernetes.client


def worker_pod(name, method, url, repetition):
    if repetition == 1:
        return yaml.safe_load(f"""
            apiVersion: v1
            kind: Pod
            spec:
              restartPolicy: Never
              containers:
              - name: {name}
                image: quay.io/loodsemanuel/curl:latest
                args:
                - "-X"
                - "{method}"
                - "{url}"
        """)
    elif repetition > 1:
        return yaml.safe_load(f"""
            apiVersion: v1
            kind: Pod
            spec:
              restartPolicy: Never
              containers:
              - name: {name}
                image: quay.io/loodsemanuel/curl:latest
                command: [ "bash", "-c", "for", "i", "in", "$(seq 1 {repetition});", "do", "curl", "-X {method} {url};", "done" ]
        """)
    else:
        return yaml.safe_load(f"""
            apiVersion: v1
            kind: Pod
            spec:
              restartPolicy: Never
              containers:
              - name: {name}
                image: quay.io/loodsemanuel/curl:latest
                command: [ "bash", "-c", "sleep", "120" ]
        """)


@kopf.on.create('example.org', 'v1', 'loadtests')
def create_function(body, spec, **kwargs):

    v1 = kubernetes.client.CoreV1Api()

    try:
        service = v1.read_namespaced_service(name=spec.test.serviceName, namespace=body.metadata.namespace)
    except:
        return {'state': 'failed'}
    
    port = 80

    for i in service.spec.ports:
        if i.name == spec.test.port:
            port = i.port

    pod = worker_pod(name="test", method=spec.test.method, url=service.metadata.name + service.metadata.namespace + ".svc:" + str(port) + "/" + spec.test.path, repetition=spec.test.repeat)

    # Make the pod a child of our custom resource object by adding namespace, labels etc to the pod definition
    kopf.adopt(pod, owner=body)

    # Create the pod in kubernetes
    if spec.replicas == 1:
        created = v1.create_namespaced_pod(namespace=pod['metadata']['namespace'], body=pod)
        return {'children': [created.metadata.uid]}
    elif spec.replicas > 1:
        children = []
        for x in range(0, spec.replicas-1):
            pod.metadata.name = pod.metadata.name + "-" + str(x)
            created = v1.create_namespaced_pod(namespace=pod['metadata']['namespace'], body=pod)
            children.append(created.metadata.uid)
        return {'children': children}
    else:
        return {'state': 'failed'}

    # Now "register" the pod with our SimpleDeployment
    return {'children': [pod.metadata.uid]}
